#!/usr/bin/env python3
"""Rendered-output gates for the Ragnarok V2 production pipeline.

These checks deliberately inspect the encoded MP4 as well as the timeline and
captions.  They are episode-agnostic: an episode supplies its own scene
boundaries, visual beats, and narration timings.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from statistics import median
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "batch_01"
FFMPEG = Path(shutil.which("ffmpeg") or (Path.home() / "Wan2GP" / "ffmpeg_bins" / "ffmpeg.exe"))
FFPROBE = Path(shutil.which("ffprobe") or (Path.home() / "Wan2GP" / "ffmpeg_bins" / "ffprobe.exe"))
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


def frame_bytes(video: Path, timestamp: float, width: int = 32, height: int = 57) -> bytes:
    # Small raw frames make the gate fast and keep the audit lightweight.
    p = subprocess.run(
        [str(FFMPEG), "-v", "error", "-ss", f"{max(0.0, timestamp):.3f}", "-i", str(video),
         "-frames:v", "1", "-vf", f"scale={width}:{height},format=gray", "-f", "rawvideo", "pipe:1"],
        cwd=ROOT, check=True, capture_output=True,
    )
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
        from .line_artifact_agent import inspect_video
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

    caption_text = " ".join(str(c.get("text", "")) for c in captions)
    source_for_agents = json.loads(source_path.read_text(encoding="utf-8")) if (source_path := epdir / "source.json").exists() else {}
    agent_reports: dict[str, Any] = {}
    if POLICY.get("name_spelling_review", {}).get("enabled") and source_for_agents:
        from .name_spelling_agent import inspect_episode as inspect_names
        agent_reports["name_spelling"] = inspect_names(source_for_agents, caption_text)
        if agent_reports["name_spelling"]["status"] == "FAIL":
            errors.append("name spelling agent found a caption mismatch or misspelling")
    if POLICY.get("historical_scene_review", {}).get("enabled") and source_for_agents:
        from .historical_scene_agent import inspect_episode as inspect_history
        agent_reports["historical_scene"] = inspect_history(source_for_agents)
        if agent_reports["historical_scene"]["status"] == "FAIL":
            errors.append("historical scene agent found a declared visual contradiction")
    if POLICY.get("wording_review", {}).get("enabled") and source_for_agents:
        from .wording_agent import inspect_episode as inspect_wording
        agent_reports["wording"] = inspect_wording(source_for_agents, caption_text)
        if agent_reports["wording"]["status"] == "FAIL":
            errors.append("wording agent found repetitive or awkward narration wording")
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
            if any(term in prompt for term in forbidden):
                errors.append(f"scene S{index:02d} image prompt contains a forbidden low-fidelity style term")
        style_text = " ".join([str(reference.get("style_board_prompt", "")), art_style]).lower()
        if any(term in style_text for term in POLICY.get("artwork", {}).get("forbidden_style_terms", [])):
            errors.append("authoritative art direction contains a forbidden low-fidelity style term")
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
        trigger_terms = [str(term).lower() for term in medieval_gate.get("trigger_terms", [])]
        if medieval_gate.get("enabled") and episode_number >= int(medieval_gate.get("minimum_episode_number", 31)) and any(term in trigger_text for term in trigger_terms):
            missing = [term for term in medieval_gate.get("required_terms", []) if str(term).lower() not in style_text]
            if missing and medieval_gate.get("fail_on_missing_direction", True):
                errors.append("medieval European art-direction gate missing required terms: " + ", ".join(missing))
            for index, scene_spec in enumerate(source.get("scenes", []), 1):
                prompt = str(scene_spec.get("image_prompt", "")).lower()
                if "pre-raphaelite" not in prompt or "medieval realism" not in prompt:
                    errors.append(f"scene S{index:02d} does not carry the required medieval European Pre-Raphaelite direction")
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
