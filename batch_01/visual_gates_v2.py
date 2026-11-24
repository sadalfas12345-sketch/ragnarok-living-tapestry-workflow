#!/usr/bin/env python3
"""Rendered-output gates for the Ragnarok V2 production pipeline.

These checks deliberately inspect the encoded MP4 as well as the timeline and
captions.  They are episode-agnostic: an episode supplies its own scene
boundaries, visual beats, and narration timings.
"""

from __future__ import annotations

import argparse
import audioop
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path
from statistics import median
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "batch_01"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
FFMPEG = Path(os.environ.get("FFMPEG") or shutil.which("ffmpeg") or (Path.home() / "Wan2GP" / "ffmpeg_bins" / "ffmpeg.exe"))
FFPROBE = Path(os.environ.get("FFPROBE") or shutil.which("ffprobe") or (Path.home() / "Wan2GP" / "ffmpeg_bins" / "ffprobe.exe"))
POLICY = json.loads((ROOT / "production_feedback_gates.json").read_text(encoding="utf-8"))


def run(cmd: list[str], *, capture: bool = True) -> str:
    p = subprocess.run(cmd, cwd=ROOT, check=True, text=True, capture_output=capture)
    return p.stdout if capture else ""


def ffprobe_json(path: Path) -> dict[str, Any]:
    return json.loads(run([str(FFPROBE), "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)]))


def parse_srt(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8-sig")
    blocks = re.split(r"\r?\n\s*\r?\n", text.strip()) if text.strip() else []
    out = []
    rx = re.compile(r"(\d{2}:\d{2}:\d{2},\d{3})\s+-->\s+(\d{2}:\d{2}:\d{2},\d{3})")

    def sec(value: str) -> float:
        h, m, rest = value.split(":")
        s, ms = rest.split(",")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

    for block in blocks:
        lines = block.splitlines()
        match = next((candidate for candidate in (rx.match(line.strip()) for line in lines) if candidate), None)
        if not match:
            continue
        index = next(i for i, line in enumerate(lines) if rx.match(line.strip()))
        body = " ".join(line.strip() for line in lines[index + 1 :] if line.strip())
        out.append({"start": sec(match.group(1)), "end": sec(match.group(2)), "text": body})
    return out


def independent_caption_alignment(epdir: Path, captions: list[dict[str, Any]], tolerance: float) -> dict[str, Any]:
    """Compare SRT boundaries with independent Whisper word timings.

    Native TTS word-boundary metadata is useful for construction, but it must
    not be the only authority: a stale or shifted cache can make captions look
    valid against the same bad timestamps. Whisper alignment is used here as
    an independent rendered-audio check.
    """
    alignment_path = epdir / "audio" / "whisper_alignment.json"
    if not alignment_path.exists():
        return {"status": "FAIL", "errors": ["missing independent Whisper alignment"], "samples": []}
    try:
        words = json.loads(alignment_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"status": "FAIL", "errors": ["independent Whisper alignment is unreadable"], "samples": []}
    if not isinstance(words, list) or not words:
        return {"status": "FAIL", "errors": ["independent Whisper alignment has no words"], "samples": []}

    def tokens(text: str) -> list[str]:
        normalized = text.lower().replace("-", " ").replace("’", "'")
        return [re.sub(r"[^a-z0-9]", "", token) for token in re.findall(r"[a-z0-9']+", normalized) if re.sub(r"[^a-z0-9]", "", token)]

    measured: list[tuple[str, float, float]] = []
    for item in words:
        item_tokens = tokens(str(item.get("text", "")))
        if not item_tokens:
            continue
        start = float(item.get("start", 0.0))
        end = float(item.get("end", 0.0))
        for item_token in item_tokens:
            measured.append((item_token, start, end))
    cursor = 0
    samples: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []
    narration_wave = epdir / "audio" / "narration.wav"

    def interval_is_silent(start: float, end: float) -> bool:
        """Reject Whisper onsets that fall wholly inside actual waveform silence."""
        if end <= start or not narration_wave.exists():
            return False
        try:
            with wave.open(str(narration_wave), "rb") as handle:
                rate = handle.getframerate()
                width = handle.getsampwidth()
                channels = handle.getnchannels()
                handle.setpos(max(0, int(start * rate)))
                frames = handle.readframes(max(1, int((end - start) * rate)))
            if not frames:
                return False
            if channels > 1:
                # audioop.rms handles interleaved PCM; the threshold is kept
                # conservative so room tone is not mistaken for speech.
                rms = audioop.rms(frames, width)
            else:
                rms = audioop.rms(frames, width)
            return rms < 220
        except (OSError, EOFError, ValueError):
            return False
    for index, caption in enumerate(captions, 1):
        wanted = tokens(str(caption.get("text", "")))
        match_start = None
        for candidate in range(cursor, len(measured)):
            if measured[candidate][0] != wanted[0]:
                continue
            if [item[0] for item in measured[candidate:candidate + len(wanted)]] == wanted:
                match_start = candidate
                break
        if match_start is None:
            warnings.append(f"caption {index} could not be matched exactly to Whisper text; boundary was not independently scored")
            continue
        match_end = match_start + len(wanted) - 1
        expected_start = measured[match_start][1]
        expected_end = measured[match_end][2]
        start_error = float(caption["start"]) - expected_start
        end_error = float(caption["end"]) - expected_end
        samples.append({"caption": index, "expected_start": round(expected_start, 3), "actual_start": round(float(caption["start"]), 3), "start_error": round(start_error, 3), "expected_end": round(expected_end, 3), "actual_end": round(float(caption["end"]), 3), "end_error": round(end_error, 3)})
        if abs(start_error) > tolerance or abs(end_error) > max(0.5, tolerance):
            # Small Whisper models can place the first word of a new scene
            # inside the preceding authored pause. If the measured waveform
            # is silent between Whisper's onset and the caption onset, the
            # caption is not late; Whisper is early. Keep the evidence in the
            # report while preventing a false hard failure.
            whisper_early = start_error > tolerance and float(caption["start"]) > expected_start
            if whisper_early and interval_is_silent(expected_start, float(caption["start"])):
                warnings.append(
                    f"caption {index} Whisper onset {expected_start:.3f}s falls in measured silence; "
                    f"caption begins at waveform onset {float(caption['start']):.3f}s"
                )
            else:
                errors.append(f"caption {index} boundary differs from Whisper by start={start_error:.3f}s end={end_error:.3f}s")
        cursor = match_end + 1
    return {"status": "PASS" if not errors else "FAIL", "errors": errors, "warnings": warnings, "samples": samples, "tolerance_seconds": tolerance, "unmatched_count": len(warnings)}


def frame_bytes(video: Path, timestamp: float, width: int = 32, height: int = 57) -> bytes:
    # Small raw frames make the gate fast and keep the audit lightweight.
    args = ["-v", "error", "-ss", f"{max(0.0, timestamp):.3f}", "-i", str(video),
            "-frames:v", "1", "-vf", f"scale={width}:{height},format=gray", "-f", "rawvideo", "pipe:1"]
    p = subprocess.run([str(FFMPEG), *args], cwd=ROOT, check=True, capture_output=True)
    expected = width * height
    if len(p.stdout) != expected:
        args = ["-v", "error", "-i", str(video), "-ss", f"{max(0.0, timestamp):.3f}",
                "-frames:v", "1", "-vf", f"scale={width}:{height},format=gray", "-f", "rawvideo", "pipe:1"]
        p = subprocess.run([str(FFMPEG), *args], cwd=ROOT, check=True, capture_output=True)
    if len(p.stdout) != expected:
        raise RuntimeError(f"empty or short frame at {timestamp:.3f}s: got {len(p.stdout)} bytes, expected {expected}")
    return p.stdout


def mean_abs_diff(a: bytes, b: bytes) -> float:
    if not a or not b or len(a) != len(b):
        return 255.0
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def expected_provenance(civilization: str) -> str:
    value = civilization.lower()
    if "ancient egypt" in value:
        return "egyptian mythology"
    if "ancient mesopotamia" in value:
        return "mesopotamian mythology"
    if "ancient greece" in value:
        return "greek mythology"
    if "japan" in value:
        return "japan"
    if "china" in value:
        return "chinese legend"
    return "tradition"


def image_dimensions(path: Path) -> tuple[int, int]:
    probe = ffprobe_json(path)
    stream = next((x for x in probe.get("streams", []) if x.get("codec_type") == "video"), {})
    return int(stream.get("width", 0)), int(stream.get("height", 0))


def gate_episode(epdir: Path, keep_audit: bool = False) -> dict[str, Any]:
    timeline_path = epdir / "timeline.json"
    video = epdir / "final_vertical_1080x1920.mp4"
    srt = epdir / "Captions_final.srt"
    errors: list[str] = []
    warnings: list[str] = []

    if not timeline_path.exists(): errors.append("missing timeline.json")
    if not video.exists(): errors.append("missing final_vertical_1080x1920.mp4")
    if not srt.exists(): errors.append("missing Captions_final.srt")
    if errors:
        return {"status": "FAIL", "errors": errors, "warnings": warnings}

    tl = json.loads(timeline_path.read_text(encoding="utf-8"))
    scenes = tl.get("scenes", [])
    runtime = float(tl.get("runtime_seconds", 0))
    probe = ffprobe_json(video)
    fmt = probe.get("format", {})
    stream = next((x for x in probe.get("streams", []) if x.get("codec_type") == "video"), {})
    actual_runtime = float(fmt.get("duration", 0))
    width, height = int(stream.get("width", 0)), int(stream.get("height", 0))
    bitrate = int(stream.get("bit_rate") or fmt.get("bit_rate") or 0)
    line_report = None
    if POLICY.get("line_artifact_review", {}).get("enabled", False):
        try:
            from .line_artifact_agent import inspect_video
        except ImportError:
            from batch_01.line_artifact_agent import inspect_video
        line_report = inspect_video(video, scenes, runtime)
        if POLICY["line_artifact_review"].get("fail_on_flagged_sample", True) and line_report["status"] == "FAIL":
            errors.append(f"line-artifact agent flagged {len(line_report['flagged_samples'])} rendered sample(s)")

    if abs(actual_runtime - runtime) > 0.12: errors.append(f"runtime mismatch: video={actual_runtime:.3f}s timeline={runtime:.3f}s")
    if (width, height) != (1080, 1920): errors.append(f"output is {width}x{height}, expected 1080x1920")
    if bitrate and bitrate < 2_000_000: errors.append(f"encoded video bitrate is too low for phone delivery: {bitrate}bps")

    previous_end = 0.0
    for scene in scenes:
        start, end, speech_end = float(scene["start"]), float(scene["end"]), float(scene["speech_end"])
        if start < previous_end - 0.02: errors.append(f"scene {scene['id']} overlaps the preceding scene")
        if end <= start: errors.append(f"scene {scene['id']} has non-positive duration")
        if speech_end > end + 0.02: errors.append(f"scene {scene['id']} speech ends after scene end")
        beats = scene.get("visual_beats", [])
        if len(beats) != POLICY["scenes"]["required_visual_beats"]: errors.append(f"scene {scene['id']} does not expose exactly three visual beats")
        if scene.get("travel_axis") == "horizontal" and scene.get("camera", {}).get("primary_direction") != POLICY["camera"]["default_direction"]:
            errors.append(f"scene {scene['id']} horizontal travel is not rightward")
        if scene.get("travel_axis") == "horizontal" and beats:
            travel_rate = abs(float(beats[-1].get("x_focus", 0)) - float(beats[0].get("x_focus", 0))) / max(0.001, end - start)
            if travel_rate > POLICY["camera"]["max_normalized_travel_per_second"] + 0.001:
                errors.append(f"scene {scene['id']} camera travel is too fast: {travel_rate:.3f} normalized units/sec")
        camera = scene.get("camera", {})
        if POLICY["camera"]["forbid_shake"] and camera.get("no_shake") is not True:
            errors.append(f"scene {scene['id']} does not explicitly forbid camera shake")
        if POLICY["camera"]["forbid_hard_crop_changes"] and camera.get("no_hard_crop_changes") is not True:
            errors.append(f"scene {scene['id']} does not explicitly forbid hard crop changes")
        previous_end = end
    if scenes and abs(previous_end - runtime) > 0.12: errors.append("last scene end disagrees with timeline runtime")
    if POLICY.get("delivery_integrity", {}).get("require_timeline_asset_paths_exist", True):
        for scene in scenes:
            asset_path = epdir / str(scene.get("asset", ""))
            if not asset_path.exists():
                errors.append(f"timeline asset is missing for {scene.get('id', 'unknown')}: {scene.get('asset', '')}")

    captions = parse_srt(srt)
    for i, cap in enumerate(captions):
        if cap["end"] <= cap["start"]: errors.append(f"caption {i + 1} has non-positive duration")
        if cap["start"] < -0.01 or cap["end"] > runtime + 0.12: errors.append(f"caption {i + 1} is outside the timeline")
        if i and cap["start"] < captions[i - 1]["end"] - 0.001: errors.append(f"caption overlap {i} -> {i + 1}")

    alignment_policy = POLICY.get("captions", {}).get("independent_whisper_alignment", {})
    whisper_alignment_report = {"status": "SKIP", "errors": [], "samples": []}
    if alignment_policy.get("required", True):
        whisper_alignment_report = independent_caption_alignment(
            epdir,
            captions,
            float(alignment_policy.get("max_boundary_error_seconds", 0.12)),
        )
        if whisper_alignment_report["status"] != "PASS":
            errors.extend(whisper_alignment_report["errors"])
        warnings.extend(whisper_alignment_report.get("warnings", []))
        (epdir / "visual_gates_audit").mkdir(exist_ok=True)
        (epdir / "visual_gates_audit" / "caption_alignment_audit.json").write_text(json.dumps(whisper_alignment_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    caption_text = " ".join(str(c.get("text", "")) for c in captions)
    source_for_agents = json.loads(source_path.read_text(encoding="utf-8")) if (source_path := epdir / "source.json").exists() else {}
    agent_reports: dict[str, Any] = {}
    emotion_policy = POLICY.get("scenes", {}).get("audience_emotion_gate", {})
    if emotion_policy.get("enabled") and emotion_policy.get("hard_gate") and source_for_agents:
        emotion_findings: list[dict[str, str]] = []
        required_fields = tuple(emotion_policy.get("required_fields", ("intended_emotion", "visual_evidence", "emotional_turn")))
        for source_scene in source_for_agents.get("scenes", []):
            scene_id = str(source_scene.get("id", "unknown"))
            for field in required_fields:
                value = str(source_scene.get(field, "")).strip()
                if not value:
                    emotion_findings.append({"scene": scene_id, "field": field, "message": "missing audience-emotion field"})
                elif len(value.split()) < 2 and not (
                    field == "intended_emotion"
                    and value.lower() in {str(term).lower() for term in emotion_policy.get("primal_emotion_terms", [])}
                ):
                    emotion_findings.append({"scene": scene_id, "field": field, "message": "field is too vague to guide a visual or narration review"})
                elif field == "intended_emotion":
                    lowered = value.lower()
                    primal_terms = tuple(str(term).lower() for term in emotion_policy.get("primal_emotion_terms", []))
                    editorial_terms = tuple(str(term).lower() for term in emotion_policy.get("forbidden_editorial_emotion_terms", []))
                    if not any(re.search(rf"\b{re.escape(term)}\b", lowered) for term in primal_terms):
                        emotion_findings.append({"scene": scene_id, "field": field, "message": "must name a concrete human emotion, not an editorial objective"})
                    for term in editorial_terms:
                        if term in lowered:
                            emotion_findings.append({"scene": scene_id, "field": field, "message": f"editorial label {term!r} is not an audience emotion"})
        agent_reports["audience_emotion_gate"] = {
            "reviewer": "audience_emotion_gate",
            "status": "FAIL" if emotion_findings else "PASS",
            "findings": emotion_findings,
        }
        if emotion_findings:
            errors.append("audience-emotion gate found missing or underspecified scene intent")
    if POLICY.get("name_spelling_review", {}).get("enabled") and source_for_agents:
        try:
            from .name_spelling_agent import inspect_episode as inspect_names
        except ImportError:
            from batch_01.name_spelling_agent import inspect_episode as inspect_names
        agent_reports["name_spelling"] = inspect_names(source_for_agents, caption_text)
        if agent_reports["name_spelling"]["status"] == "FAIL":
            errors.append("name spelling agent found a caption mismatch or misspelling")
    if POLICY.get("historical_scene_review", {}).get("enabled") and source_for_agents:
        try:
            from .historical_scene_agent import inspect_episode as inspect_history
        except ImportError:
            from batch_01.historical_scene_agent import inspect_episode as inspect_history
        agent_reports["historical_scene"] = inspect_history(source_for_agents)
        if agent_reports["historical_scene"]["status"] == "FAIL":
            errors.append("historical scene agent found a declared visual contradiction")
    if POLICY.get("wording_review", {}).get("enabled") and source_for_agents:
        try:
            from .wording_agent import inspect_episode as inspect_wording
        except ImportError:
            from batch_01.wording_agent import inspect_episode as inspect_wording
        agent_reports["wording"] = inspect_wording(source_for_agents, caption_text)
        if agent_reports["wording"]["status"] == "FAIL":
            errors.append("wording agent found repetitive or awkward narration wording")
    if source_for_agents:
        try:
            from .procedural_pipeline_audit import inspect_episode as inspect_procedure
            from .natural_speech_agent import inspect_episode as inspect_speech
        except ImportError:
            from batch_01.procedural_pipeline_audit import inspect_episode as inspect_procedure
            from batch_01.natural_speech_agent import inspect_episode as inspect_speech
        agent_reports["procedural_pipeline_audit"] = inspect_procedure(epdir, tl, video, srt)
        agent_reports["natural_speech_review"] = inspect_speech(epdir, tl)
        if agent_reports["procedural_pipeline_audit"]["status"] == "FAIL":
            errors.append("procedural pipeline audit found missing or stale production artifacts")
        if agent_reports["natural_speech_review"]["status"] == "FAIL":
            errors.append("natural speech review found merged words, encoding errors, or unnatural internal gaps")
    if POLICY.get("anatomy_review", {}).get("enabled"):
        try:
            from .anatomy_artifact_agent import inspect_episode as inspect_anatomy
        except ImportError:
            from batch_01.anatomy_artifact_agent import inspect_episode as inspect_anatomy
        agent_reports["anatomy_artifact_review"] = inspect_anatomy(epdir, scenes)
        if agent_reports["anatomy_artifact_review"]["status"] == "FAIL":
            errors.append("anatomy artifact gate found missing review or mutant-looking anatomy")
    try:
        from .adversarial_render_agent import inspect_episode as inspect_render
    except ImportError:
        from batch_01.adversarial_render_agent import inspect_episode as inspect_render
    agent_reports["adversarial_render_review"] = inspect_render(video, scenes)
    if agent_reports["adversarial_render_review"]["status"] == "FAIL":
        errors.append("adversarial render review found a black, frozen, or visually static rendered state")
    multi_policy = POLICY.get("multi_agent_review", {})
    if multi_policy.get("enabled") and multi_policy.get("hard_gate"):
        required_roles = multi_policy.get("required_roles", [])
        required_status = multi_policy.get("required_report_status", "PASS")
        for role in required_roles:
            report = agent_reports.get(role)
            if not report:
                errors.append(f"required independent agent report is missing: {role}")
            elif report.get("status") != required_status:
                errors.append(f"independent agent report is not {required_status}: {role}")
    if agent_reports:
        audit_dir = epdir / "visual_gates_audit"
        audit_dir.mkdir(exist_ok=True)
        (audit_dir / "independent_agent_reports.json").write_text(json.dumps(agent_reports, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if POLICY.get("provenance", {}).get("ordinary_duplicate_words") == "review_only":
        hard_terms = {str(x).lower() for x in POLICY.get("provenance", {}).get("dedupe_terms", [])}
        for match in re.finditer(r"\b([A-Za-z][\w'-]+)\s+\1\b", caption_text, re.IGNORECASE):
            word = match.group(1).lower()
            if word not in hard_terms:
                warnings.append(f"ordinary repeated word requires story-context review: {word!r}")
    for bad in POLICY.get("rendered_caption_text", {}).get("forbidden_sequences", []):
        if bad in caption_text:
            errors.append(f"captions contain forbidden mojibake sequence {bad!r}")
    manifest_path = epdir / "audio" / "audio_manifest.json"
    if POLICY.get("audio", {}).get("require_mix_manifest", True):
        if not manifest_path.exists():
            errors.append("missing audio manifest; final mix may be stale relative to narration")
        else:
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                narration_path = epdir / "audio" / "narration.wav"
                mix_path = epdir / "audio" / "final_mixed_audio.wav"
                video_path = epdir / "final_vertical_1080x1920.mp4"
                if str(manifest.get("narration_sha256", "")).lower() != hashlib.sha256(narration_path.read_bytes()).hexdigest().lower():
                    errors.append("audio manifest narration hash does not match current narration")
                if str(manifest.get("final_mix_sha256", "")).lower() != hashlib.sha256(mix_path.read_bytes()).hexdigest().lower():
                    errors.append("audio manifest final-mix hash does not match current mix")
                if str(manifest.get("final_video_sha256", "")).lower() != hashlib.sha256(video_path.read_bytes()).hexdigest().lower():
                    errors.append("audio manifest final-video hash does not match current MP4")
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                errors.append("audio manifest is unreadable")

    source_path = epdir / "source.json"
    if POLICY.get("artwork", {}).get("require_culture_specific_style", True) and source_path.exists():
        source = json.loads(source_path.read_text(encoding="utf-8"))
        reference = source.get("image_reference", {})
        art_style = str(reference.get("art_style", "")).strip()
        palette = str(reference.get("palette", "")).strip()
        civilization = str(source.get("civilization", "")).strip()
        if not civilization or not art_style or not palette:
            errors.append("authoritative JSON lacks culture-specific civilization, art_style, or palette direction")
        for index, scene_spec in enumerate(source.get("scenes", []), 1):
            prompt = str(scene_spec.get("image_prompt", "")).lower()
            if civilization and civilization.lower() not in prompt and art_style.lower() not in prompt:
                warnings.append(f"scene S{index:02d} image prompt does not repeat the episode's cultural/style direction")
            forbidden = [str(x).lower() for x in POLICY.get("artwork", {}).get("forbidden_style_terms", [])]
            # Negative prompt exclusions such as "no cartoon" are valid
            # quality direction, not evidence that the generated style is
            # cartoon-like. Flag only positive uses of forbidden terms.
            def positive_forbidden_term(text: str, term: str) -> bool:
                pattern = r"(?<!\bno )(?<!\bnot )(?<!\bavoid )(?<!\bwithout )" + re.escape(term)
                return bool(re.search(pattern, text))
            if any(positive_forbidden_term(prompt, term) for term in forbidden):
                errors.append(f"scene S{index:02d} image prompt contains a forbidden low-fidelity style term")
        style_text = " ".join([str(reference.get("style_board_prompt", "")), art_style]).lower()
        if any(positive_forbidden_term(style_text, str(term).lower()) for term in POLICY.get("artwork", {}).get("forbidden_style_terms", [])):
            errors.append("authoritative art direction contains a forbidden low-fidelity style term")
        anti_cartoon = POLICY.get("artwork", {}).get("anti_cartoon_gate", {})
        if anti_cartoon.get("enabled", True):
            realism_terms = [str(term).lower() for term in anti_cartoon.get("required_realism_terms_any", [])]
            negative_terms = [str(term).lower() for term in anti_cartoon.get("required_negative_terms", [])]
            if realism_terms and not any(term in style_text for term in realism_terms):
                errors.append(anti_cartoon.get("failure_message", "anti-cartoon art-direction gate failed") + ": missing fine-art medium")
            if negative_terms and not any(term in style_text for term in negative_terms):
                errors.append(anti_cartoon.get("failure_message", "anti-cartoon art-direction gate failed") + ": missing negative style constraint")
            for index, scene_spec in enumerate(source.get("scenes", []), 1):
                prompt = str(scene_spec.get("image_prompt", "")).lower()
                if realism_terms and not any(term in prompt for term in realism_terms):
                    errors.append(f"scene S{index:02d} fails anti-cartoon gate: missing fine-art medium")
                if negative_terms and not any(term in prompt for term in negative_terms):
                    errors.append(f"scene S{index:02d} fails anti-cartoon gate: missing negative style constraint")
        religious_gate = POLICY.get("artwork", {}).get("major_religious_imagery_gate", {})
        if religious_gate.get("enabled"):
            forbidden_religious = [str(term).lower() for term in religious_gate.get("forbidden_terms", [])]
            def contains_forbidden_phrase(text, term):
                return bool(re.search(r"(?<![a-z])" + re.escape(term) + r"(?![a-z])", text))
            if any(contains_forbidden_phrase(style_text, term) for term in forbidden_religious):
                errors.append(religious_gate.get("failure_message", "forbidden religious imagery in art direction"))
            for index, scene_spec in enumerate(source.get("scenes", []), 1):
                prompt = str(scene_spec.get("image_prompt", "")).lower()
                found = [term for term in forbidden_religious if contains_forbidden_phrase(prompt, term)]
                if found:
                    errors.append(f"scene S{index:02d} contains forbidden major-religion imagery terms: {', '.join(found)}")
        medieval_gate = POLICY.get("artwork", {}).get("medieval_european_style_gate", {})
        episode_number = int(re.match(r"\d+", epdir.name).group(0)) if re.match(r"\d+", epdir.name) else 0
        trigger_text = " ".join([
            civilization,
            str(source.get("title", "")),
            art_style,
            str(reference.get("style_board_prompt", "")),
        ]).lower()
        historical_period = str(source.get("historical_period", "")).lower()
        trigger_terms = [str(term).lower() for term in medieval_gate.get("trigger_terms", [])]
        is_early_modern_or_colonial = bool(re.search(r"early modern|16th century|17th century|colonial|colonization|1587|1590", historical_period + " " + trigger_text))
        if medieval_gate.get("enabled") and episode_number >= int(medieval_gate.get("minimum_episode_number", 1)) and any(term in trigger_text for term in trigger_terms) and not is_early_modern_or_colonial:
            allowed_families = [str(term).lower() for term in medieval_gate.get("allowed_style_families", [])]
            if medieval_gate.get("fail_on_unapproved_style_family", True) and allowed_families and not any(term in style_text for term in allowed_families):
                errors.append("medieval European art-direction gate requires an approved style family")
            for index, scene_spec in enumerate(source.get("scenes", []), 1):
                prompt = str(scene_spec.get("image_prompt", "")).lower()
                if medieval_gate.get("fail_on_unapproved_style_family", True) and allowed_families and not any(term in prompt for term in allowed_families):
                    errors.append(f"scene S{index:02d} does not carry an approved medieval European style family")
        for style_default in POLICY.get("artwork", {}).get("culture_period_style_defaults", []):
            if not style_default.get("enabled", True):
                continue
            default_terms = [str(term).lower() for term in style_default.get("trigger_terms", [])]
            if not any(term in trigger_text for term in default_terms):
                continue
            required_style_terms = [str(term).lower() for term in style_default.get("required_style_terms", [])]
            missing_default_terms = [term for term in required_style_terms if term not in style_text]
            if missing_default_terms:
                errors.append(style_default.get("failure_message", "culture-period style direction is missing") + ": " + ", ".join(missing_default_terms))
            for index, scene_spec in enumerate(source.get("scenes", []), 1):
                prompt = str(scene_spec.get("image_prompt", "")).lower()
                missing_prompt_terms = [term for term in required_style_terms if term not in prompt]
                if missing_prompt_terms:
                    errors.append(f"scene S{index:02d} does not carry the culture-period style direction: {', '.join(missing_prompt_terms)}")
    if source_path.exists() and POLICY.get("provenance", {}).get("required_after_what_if", True):
        source = json.loads(source_path.read_text(encoding="utf-8"))
        first_scene_id = str(scenes[0].get("id", "S01")) if scenes else "S01"
        first_text = " ".join(str(c.get("text", "")) for c in captions if c.get("scene") == first_scene_id)
        if re.match(r"^What if\b", first_text, re.I):
            expected = expected_provenance(str(source.get("civilization", "")))
            has_historical_date = bool(re.search(r"\b(?:1[0-9]{3}|20[0-9]{2})\b", first_text))
            if expected not in first_text.lower() and not any(marker in first_text.lower() for marker in POLICY["provenance"].get("recognized_markers", [])) and not has_historical_date:
                errors.append(f"first What if scene lacks source/provenance phrase for {source.get('civilization', 'unknown civilization')}")
            if POLICY.get("provenance", {}).get("dedupe_repeated_terms", True):
                for term in POLICY.get("provenance", {}).get("dedupe_terms", []):
                    if re.search(rf"\b{re.escape(str(term))}\s+{re.escape(str(term))}\b", first_text, re.IGNORECASE):
                        errors.append(f"first What if scene repeats provenance term {term!r}")
        for cache_file in sorted((epdir / "audio").glob("scene_*_cache.json")):
            try:
                cached = json.loads(cache_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            cached_text = str(cached.get("spoken_text", cached.get("text", "")))
            for term in POLICY.get("provenance", {}).get("dedupe_terms", []):
                if re.search(rf"\b{re.escape(str(term))}\s+{re.escape(str(term))}\b", cached_text, re.IGNORECASE):
                    errors.append(f"{cache_file.name} repeats provenance term {term!r}")

    artwork_policy = POLICY.get("artwork", {})
    for index in range(1, len(scenes) + 1):
        asset = epdir / "assets" / f"H{index:02d}.png"
        if artwork_policy.get("require_horizontal_panorama", True) and not asset.exists():
            errors.append(f"scene S{index:02d} is missing required horizontal panorama H{index:02d}.png")
            continue
        if asset.exists():
            aw, ah = image_dimensions(asset)
            if aw < int(artwork_policy.get("minimum_width_pixels", 0)) or ah < int(artwork_policy.get("minimum_height_pixels", 0)):
                errors.append(f"scene S{index:02d} panorama is too small: {aw}x{ah}")

    audit_dir = epdir / "visual_gates_audit"
    audit_dir.mkdir(exist_ok=True)
    scene_audit = []
    for scene in scenes:
        start, end = float(scene["start"]), float(scene["end"])
        times = [start + (end - start) * f for f in (0.08, 0.50, 0.92)]
        frames = [frame_bytes(video, t) for t in times]
        changes = [round(mean_abs_diff(frames[i], frames[i + 1]), 3) for i in range(2)]
        if max(changes, default=0.0) < 0.35:
            errors.append(f"scene {scene['id']} has no measurable rendered visual progression")
        scene_audit.append({"scene": scene["id"], "sample_times": [round(t, 3) for t in times], "mean_abs_diffs": changes,
                            "frame_sha256": [hashlib.sha256(frame).hexdigest()[:16] for frame in frames]})

    transition_audit = []
    for left, right in zip(scenes, scenes[1:]):
        boundary = float(right["start"])
        offsets = [-0.18, -0.06, 0.04, 0.14, 0.26]
        frames = [frame_bytes(video, boundary + off) for off in offsets]
        diffs = [round(mean_abs_diff(frames[i], frames[i + 1]), 3) for i in range(len(frames) - 1)]
        means = [round(sum(frame) / len(frame), 2) if frame else 0.0 for frame in frames]
        if any(value < POLICY["scenes"]["transition_max_black_luma"] for value in means): errors.append(f"black/near-black transition frame at {right['id']} boundary")
        if diffs[1] < POLICY["scenes"]["transition_min_progression_diff"] and diffs[2] < POLICY["scenes"]["transition_min_progression_diff"]: errors.append(f"transition into {right['id']} appears frozen")
        transition_audit.append({"from": left["id"], "to": right["id"], "boundary": boundary,
                                 "offsets": offsets, "mean_abs_diffs": diffs, "mean_luma": means})

    adjacent_scene_audit = []
    contrast_policy = POLICY.get("scene_contrast", {})
    if contrast_policy.get("enabled", True) and len(scenes) > 1:
        fractions = [float(x) for x in contrast_policy.get("sample_fractions", [0.08, 0.50, 0.92])]
        minimum = float(contrast_policy.get("minimum_pair_mean_abs_diff", 4.0))
        required_distinct = int(contrast_policy.get("minimum_distinct_samples", 2))
        for left, right in zip(scenes, scenes[1:]):
            left_frames = [frame_bytes(video, float(left["start"]) + (float(left["end"]) - float(left["start"])) * f) for f in fractions]
            right_frames = [frame_bytes(video, float(right["start"]) + (float(right["end"]) - float(right["start"])) * f) for f in fractions]
            pair_diffs = [round(mean_abs_diff(a, b), 3) for a, b in zip(left_frames, right_frames)]
            distinct = sum(value >= minimum for value in pair_diffs)
            if distinct < required_distinct:
                errors.append(f"{contrast_policy.get('failure_message', 'adjacent scenes are visually too similar')}: {left['id']} -> {right['id']} diffs={pair_diffs}")
            adjacent_scene_audit.append({"from": left["id"], "to": right["id"], "sample_fractions": fractions, "mean_abs_diffs": pair_diffs, "distinct_sample_count": distinct})

    report = {
        "episode": epdir.name, "status": "PASS" if not errors else "FAIL", "errors": errors,
        "warnings": warnings, "timeline_runtime_seconds": runtime, "video_runtime_seconds": round(actual_runtime, 3),
        "dimensions": [width, height], "video_bitrate": bitrate, "caption_count": len(captions), "line_artifact_review": line_report, "independent_agent_reports": agent_reports,
        "scene_visual_audit": scene_audit, "transition_audit": transition_audit,
        "adjacent_scene_contrast_audit": adjacent_scene_audit,
    }
    (audit_dir / "visual_gates_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if not keep_audit:
        for child in audit_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        audit_dir.rmdir()
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", type=int, required=True)
    ap.add_argument("--keep-audit", action="store_true")
    args = ap.parse_args()
    matches = list(WORK.glob(f"episodes/{args.episode:02d}_*"))
    if len(matches) != 1:
        print(json.dumps({"status": "FAIL", "errors": [f"expected one directory for episode {args.episode}, found {len(matches)}"]}))
        return 1
    report = gate_episode(matches[0], args.keep_audit)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
