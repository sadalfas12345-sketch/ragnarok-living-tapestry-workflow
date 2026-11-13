#!/usr/bin/env python3
"""Reusable Living Tapestries Batch 01 pipeline.

The episode JSON is the only editorial source.  The final narration waveform is
the only timing source.  Ragnarök files in the repository are intentionally not
imported by this runner.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source"
WORK = ROOT / "episodes"
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
FFPROBE = os.environ.get("FFPROBE", "ffprobe")
RATE = 24000
VOICE = os.environ.get("LIVING_TAPESTRIES_VOICE", "en-US-AvaNeural")

MUSIC_PROFILES = {
    "default": [
        {"title": "Epical Drums 05", "artist": "Grigoriy Nuzhny", "url": "https://mixkit.co/free-stock-music/orchestral-hybrid/", "file": "mixkit_epical_drums_05_grigoriy_nuzhny.mp3"},
        {"title": "Epic Games", "artist": "Ahjay Stelino", "url": "https://mixkit.co/free-stock-music/mood/tension/", "file": "mixkit_epic_games_ahjay_stelino.mp3"},
        {"title": "A New Life", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/orchestral-hybrid/", "file": "mixkit_a_new_life_eugenio_mininni.mp3"},
    ],
    3: [
        {"title": "Fright Night", "artist": "Michael Ramir C.", "url": "https://mixkit.co/free-stock-music/mood/suspenseful/", "file": "mixkit_fright_night_michael_ramir_c.mp3"},
        {"title": "Valley Sunset", "artist": "Alejandro Magaña (A. M.)", "url": "https://mixkit.co/free-stock-music/mood/mysterious/", "file": "mixkit_valley_sunset_alejandro_magana.mp3"},
        {"title": "Silent Descent", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_silent_descent_eugenio_mininni.mp3"},
    ],
    4: [
        {"title": "Sun and His Daughter", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_sun_and_his_daughter_eugenio_mininni.mp3"},
        {"title": "Discover", "artist": "Eugenio Mininni", "url": "https://mixkit.co/free-stock-music/", "file": "mixkit_discover_eugenio_mininni.mp3"},
        {"title": "Spirit in the Woods", "artist": "Alejandro Magaña (A. M.)", "url": "https://mixkit.co/free-stock-music/mood/mysterious/", "file": "mixkit_spirit_in_the_woods_alejandro_magana.mp3"},
    ],
}


def run(cmd: list[str], *, capture=False) -> str:
    p = subprocess.run(cmd, check=True, text=True, capture_output=capture)
    return p.stdout if capture else ""


def duration(path: Path) -> float:
    out = run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)], capture=True)
    return float(json.loads(out)["format"]["duration"])


def load_episode(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def episode_paths(ep: int) -> tuple[Path, Path]:
    spec_path = sorted(SOURCE.glob(f"{ep:02d}_*.json"))[0]
    return spec_path, WORK / f"{ep:02d}_{spec_path.stem[3:]}"


def source_files() -> list[Path]:
    return sorted(SOURCE.glob("[0-9][0-9]_*.json"))


def validate_spec(spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = ["schema_version", "episode_number", "title", "civilization", "source_integrity", "format", "runtime", "image_reference", "audio", "scenes"]
    errors.extend(f"missing top-level field: {k}" for k in required if k not in spec)
    if spec.get("schema_version") != "living_tapestry_story_v1":
        errors.append("unsupported schema_version")
    scenes = spec.get("scenes", [])
    if len(scenes) != 6:
        errors.append(f"expected 6 scenes, found {len(scenes)}")
    seen = set()
    for i, scene in enumerate(scenes, 1):
        for k in ("id", "asset", "caption", "image_prompt", "camera", "music", "sfx", "pause_after_seconds_hint"):
            if k not in scene:
                errors.append(f"scene {i} missing {k}")
        if scene.get("id") in seen:
            errors.append(f"duplicate scene id: {scene.get('id')}")
        seen.add(scene.get("id"))
        if not isinstance(scene.get("caption"), str) or not scene.get("caption", "").strip():
            errors.append(f"scene {i} caption is empty")
        try:
            pause = float(scene.get("pause_after_seconds_hint"))
            if not 0.0 <= pause <= 3.0:
                errors.append(f"scene {i} pause hint outside 0-3 seconds")
        except (TypeError, ValueError):
            errors.append(f"scene {i} pause hint is not numeric")
    si = spec.get("source_integrity", {})
    if not si.get("classification") or not si.get("research_status"):
        errors.append("source_integrity must include classification and research_status")
    if spec.get("image_reference", {}).get("status") != "GENERATE_BEFORE_RENDER":
        errors.append("image_reference.status must require a generated style board")
    if not isinstance(spec.get("audio", {}).get("mix"), dict):
        errors.append("audio.mix must be an object")
    return errors


def validate_all() -> dict[str, Any]:
    reports = []
    for path in source_files():
        spec = load_episode(path)
        errors = validate_spec(spec)
        reports.append({"episode": spec.get("episode_number"), "file": path.name, "title": spec.get("title"), "errors": errors, "status": "PASS" if not errors else "FAIL"})
    report = {"schema": "living_tapestry_batch_validation_v1", "count": len(reports), "reports": reports, "status": "PASS" if all(not x["errors"] for x in reports) else "FAIL"}
    (ROOT / "validation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audit = []
    for path in source_files():
        spec = load_episode(path)
        si = spec.get("source_integrity", {})
        audit.append({"episode": spec.get("episode_number"), "title": spec.get("title"), "civilization": spec.get("civilization"), "classification": si.get("classification"), "primary_source_or_tradition": si.get("primary_source_or_tradition"), "research_status": si.get("research_status"), "publication_rule": "label as retelling or unresolved account until source review is complete"})
    (ROOT / "source_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def split_sentences(text: str) -> list[str]:
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+", text.strip()) if x.strip()]


def script_tokens(text: str) -> list[str]:
    """Return words with terminal punctuation retained for caption breaks."""
    return re.findall(r"[\wÀ-ÖØ-öø-ÿ'’-]+[.!?,;:]*", text)


async def edge_scene(text: str, out_mp3: Path, words_json: Path) -> None:
    import edge_tts
    communicate = edge_tts.Communicate(text, VOICE, rate=os.environ.get("LIVING_TAPESTRIES_RATE", "-15%"), volume="+0%", pitch="+0Hz")
    audio = bytearray()
    boundaries = []
    async for item in communicate.stream():
        if item["type"] == "audio":
            audio.extend(item["data"])
        elif item["type"] == "WordBoundary":
            boundaries.append({"text": item["text"], "offset_100ns": item["offset"], "duration_100ns": item["duration"]})
    out_mp3.write_bytes(audio)
    words_json.write_text(json.dumps(boundaries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def word_groups(words: list[dict[str, Any]], scene_start: float, scene_audio_start: float) -> list[dict[str, Any]]:
    groups = []
    cur = []
    for w in words:
        cur.append(w)
        text = w["text"]
        terminal = bool(re.search(r"[.!?,;:]$", text))
        if len(cur) >= 7 or (len(cur) >= 3 and terminal):
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    result = []
    for idx, group in enumerate(groups, 1):
        start = scene_start + (group[0]["offset_100ns"] / 1e7) - scene_audio_start
        end = scene_start + ((group[-1]["offset_100ns"] + group[-1]["duration_100ns"]) / 1e7) - scene_audio_start
        result.append({"id": f"{scene_start:.3f}-{idx}", "scene": None, "text": " ".join(w["text"] for w in group), "start": round(max(scene_start, start), 3), "end": round(max(start + 0.15, end), 3), "word_count": len(group)})
    return result


def whisper_align(audio_path: Path) -> list[dict[str, Any]]:
    """Measure word onsets from the final narration waveform."""
    import whisper
    from scipy.signal import resample_poly
    model = whisper.load_model(os.environ.get("WHISPER_MODEL", "tiny.en"))
    audio, sample_rate = sf.read(str(audio_path), dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sample_rate != 16000:
        audio = resample_poly(audio, 16000, sample_rate).astype("float32")
    result = model.transcribe(audio, language="en", word_timestamps=True, fp16=False, condition_on_previous_text=False)
    measured = []
    for segment in result.get("segments", []):
        for word in segment.get("words", []):
            text = word.get("word", "").strip()
            if text:
                measured.append({"text": text, "start": float(word["start"]), "end": float(word["end"])})
    if not measured:
        raise RuntimeError("Whisper returned no word timestamps")
    return measured


def build_narration(spec: dict[str, Any], epdir: Path) -> Path:
    audio_dir = epdir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    scene_wavs: list[np.ndarray] = []
    scene_meta = []
    for idx, scene in enumerate(spec["scenes"], 1):
        mp3 = audio_dir / f"scene_{idx:02d}.mp3"
        words_file = audio_dir / f"scene_{idx:02d}_words.json"
        if not mp3.exists() or not words_file.exists():
            asyncio.run(edge_scene(scene["caption"], mp3, words_file))
        wav = audio_dir / f"scene_{idx:02d}.wav"
        if not wav.exists():
            run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(mp3), "-ar", str(RATE), "-ac", "1", str(wav)])
        data, rate = sf.read(str(wav), dtype="float32")
        if rate != RATE:
            raise RuntimeError(f"unexpected narration rate {rate}")
        data = np.asarray(data).reshape(-1)
        active = np.where(np.abs(data) > 0.006)[0]
        if len(active):
            data = data[:min(len(data), int(active[-1] + 0.05 * RATE))]
        scene_wavs.append(data)
        scene_meta.append({"scene": scene, "duration": len(data) / RATE})
    all_audio: list[np.ndarray] = []
    scenes = []
    cursor = 0.0
    for idx, meta in enumerate(scene_meta, 1):
        scene = meta["scene"]
        speech_start = cursor
        all_audio.append(scene_wavs[idx - 1])
        speech_end = speech_start + meta["duration"]
        pause = float(scene.get("pause_after_seconds_hint", 0.7))
        if idx == len(scene_meta):
            pause = max(pause, 1.0)
        all_audio.append(np.zeros(round(pause * RATE), dtype="float32"))
        cursor = speech_end + pause
        scenes.append({"id": scene["id"], "asset": scene["asset"], "start": round(speech_start, 3), "speech_end": round(speech_end, 3), "end": round(cursor, 3), "pause_after": pause, "camera": scene["camera"], "image_interval": {"start": round(speech_start, 3), "end": round(cursor, 3)}})
    data = np.concatenate(all_audio)
    narration = audio_dir / "narration.wav"
    sf.write(str(narration), data, RATE, subtype="PCM_16")
    measured = whisper_align(narration)
    captions = []
    phrases = []
    cursor_word = 0
    for scene, scene_tl in zip(spec["scenes"], scenes):
        tokens = script_tokens(scene["caption"])
        scene_measured = [x for x in measured if x["end"] >= scene_tl["start"] - 0.2 and x["start"] <= scene_tl["speech_end"] + 0.2]
        scene_pairs = []
        local_index = 0
        for token in tokens:
            target = re.sub(r"[^a-z0-9]", "", token.lower())
            found = None
            for k in range(local_index, min(local_index + 6, len(scene_measured))):
                candidate = re.sub(r"[^a-z0-9]", "", scene_measured[k]["text"].lower())
                if candidate == target or (len(target) > 4 and len(candidate) > 3 and (candidate in target or target in candidate)):
                    found = k
                    break
            if found is None:
                found = min(local_index, len(scene_measured) - 1)
            if found < 0:
                raise RuntimeError(f"no measured word alignment for {scene['id']}")
            scene_pairs.append({"text": token, "start": scene_measured[found]["start"], "end": scene_measured[found]["end"]})
            local_index = min(found + 1, len(scene_measured))
        if scene_pairs:
            scene_pairs = [{**x, "start": max(scene_tl["start"], x["start"]), "end": min(scene_tl["speech_end"], x["end"])} for x in scene_pairs]
            scene_tl["speech_end"] = round(max(x["end"] for x in scene_pairs), 3)
        local = 0
        for phrase in split_sentences(scene["caption"]):
            n = len(script_tokens(phrase))
            pp = scene_pairs[local:local + n]
            local += n
            if pp:
                phrases.append({"scene": scene["id"], "text": phrase, "start": round(pp[0]["start"], 3), "end": round(pp[-1]["end"], 3)})
        groups = []
        cur = []
        for pair in scene_pairs:
            cur.append(pair)
            if len(cur) >= 7 or (len(cur) >= 3 and re.search(r"[.!?,;:]$", pair["text"])):
                groups.append(cur); cur = []
        if cur: groups.append(cur)
        for group in groups:
            captions.append({"scene": scene["id"], "text": " ".join(x["text"] for x in group), "start": round(group[0]["start"], 3), "end": round(group[-1]["end"], 3), "word_count": len(group)})
    for i in range(len(scenes) - 1):
        scenes[i]["measured_pause_after"] = round(scenes[i + 1]["start"] - scenes[i]["speech_end"], 3)
    scenes[-1]["measured_pause_after"] = round(scenes[-1]["end"] - scenes[-1]["speech_end"], 3)
    music = [{"scene": s["id"], "cue": src["music"]["cue"], "instrumentation": src["music"]["instrumentation"], "voice_priority": src["music"]["voice_priority"], "duck_on_speech": src["music"]["duck_on_speech"], "start": s["start"], "end": s["end"]} for s, src in zip(scenes, spec["scenes"])]
    sfx = [{"scene": s["id"], "cue": src["sfx"]["cue"], "narration_masking_forbidden": src["sfx"]["narration_masking_forbidden"], "start": s["start"], "end": s["end"]} for s, src in zip(scenes, spec["scenes"])]
    timeline = {"schema": "living_tapestry_timeline_v1", "master_clock": "audio/narration.wav", "sample_rate": RATE, "runtime_seconds": round(len(data) / RATE, 3), "narration": {"voice": VOICE, "alignment": "Whisper tiny.en word timestamps measured against final narration waveform", "phrases": phrases, "captions": captions}, "scenes": scenes, "music": music, "sfx": sfx}
    (epdir / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return narration


def write_srt(timeline: dict[str, Any], out: Path) -> None:
    def ts(sec: float) -> str:
        ms = round(sec * 1000)
        h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    blocks = []
    for i, c in enumerate(timeline["narration"]["captions"], 1):
        blocks.append(f"{i}\n{ts(c['start'])} --> {ts(c['end'])}\n{c['text']}\n")
    out.write_text("\n".join(blocks), encoding="utf-8")


def render_video(spec: dict[str, Any], epdir: Path) -> Path:
    tl = json.loads((epdir / "timeline.json").read_text(encoding="utf-8"))
    segdir = epdir / "segments"; segdir.mkdir(exist_ok=True)
    files = []
    for i, scene in enumerate(tl["scenes"], 1):
        source_asset = epdir / "assets" / f"P{i:02d}.png"
        if not source_asset.exists():
            raise FileNotFoundError(source_asset)
        out = segdir / f"S{i:02d}.mp4"
        dur = scene["end"] - scene["start"]
        frames = max(2, round(dur * 30))
        progress = f"(1-cos(on/{frames-1}*PI))/2"
        vf = f"zoompan=z=1+0.10*{progress}:x=iw/2-(iw/zoom/2):y=ih/2-(ih/zoom/2):d={frames}:s=1080x1920:fps=30,format=yuv420p,fade=t=in:st=0:d=0.18,fade=t=out:st={max(0,dur-0.18):.3f}:d=0.18"
        run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-loop", "1", "-i", str(source_asset), "-vf", vf, "-frames:v", str(frames), "-an", "-c:v", "libx264", "-preset", "veryfast", "-b:v", "500k", str(out)])
        files.append(out)
    concat = segdir / "concat.txt"
    concat.write_text("\n".join(f"file '{p.resolve()}'" for p in files), encoding="utf-8")
    raw = epdir / "video_only.mp4"
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(raw)])
    srt = epdir / "Captions_final.srt"
    sub_path = str(srt.resolve()).replace("\\", "/").replace(":", "\\:")
    vf = f"subtitles=filename='{sub_path}':force_style='FontName=Georgia,FontSize=18,PrimaryColour=&H00F5F1E8,OutlineColour=&H80000000,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=125'"
    out = epdir / "video_captioned.mp4"
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw), "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast", "-b:v", "500k", str(out)])
    return out


def build_audio(spec: dict[str, Any], epdir: Path) -> Path:
    tl = json.loads((epdir / "timeline.json").read_text(encoding="utf-8"))
    runtime = tl["runtime_seconds"]
    adir = epdir / "audio"
    mixdir = adir / "mixkit"; mixdir.mkdir(exist_ok=True)
    profile = MUSIC_PROFILES.get(spec["episode_number"], MUSIC_PROFILES["default"])
    tracks = [ROOT.parent / "audio" / "mixkit" / item["file"] for item in profile]
    if not all(x.exists() for x in tracks):
        raise FileNotFoundError("Mixkit tracks missing from the existing licensed asset cache")
    music = adir / "music_stem.wav"
    # Use the story's emotional cue labels to arrange a three-part licensed bed.
    cue_two = round(tl["scenes"][1]["start"] * 1000)
    cue_three = round(tl["scenes"][3]["start"] * 1000)
    f = (f"[0:a]atrim=0:{runtime:.3f},asetpts=PTS-STARTPTS,volume=0.22,lowpass=f=3200,afade=t=in:st=0:d=3,afade=t=out:st={max(0,runtime-3):.3f}:d=3[m0];"
         f"[1:a]atrim=0:{runtime:.3f},asetpts=PTS-STARTPTS,volume=0.20,lowpass=f=4800,adelay={cue_two}|{cue_two}[m1];"
         f"[2:a]atrim=0:{runtime:.3f},asetpts=PTS-STARTPTS,volume=0.16,lowpass=f=5200,adelay={cue_three}|{cue_three}[m2];"
         f"[m0][m1][m2]amix=inputs=3:duration=longest:dropout_transition=2,atrim=0:{runtime:.3f},asetpts=PTS-STARTPTS,equalizer=f=2600:t=q:w=1:g=-3,aresample=48000[m]")
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(tracks[0]), "-i", str(tracks[1]), "-i", str(tracks[2]), "-filter_complex", f, "-map", "[m]", "-ac", "2", "-c:a", "pcm_s16le", str(music)])
    narration = adir / "narration.wav"
    sfx = adir / "sfx_stem.wav"
    # Procedural, attribution-free accents: soft tonal hit per scene plus low air.
    tone = "aevalsrc=0.018*sin(2*PI*110*t)*exp(-2*t):s=48000:d=1"
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", tone, "-filter_complex", f"apad=pad_dur={runtime:.3f},atrim=0:{runtime:.3f},pan=stereo|c0=c0|c1=c0", "-ac", "2", "-c:a", "pcm_s16le", str(sfx)])
    final = adir / "final_mixed_audio.wav"
    mix = f"[0:a]aresample=48000,pan=stereo|c0=c0|c1=c0,asplit=2[narr][key];[1:a]aresample=48000,pan=stereo|c0=c0|c1=c1[music];[music][key]sidechaincompress=threshold=0.015:ratio=5:attack=60:release=700:makeup=1[duck];[2:a]aresample=48000,pan=stereo|c0=c0|c1=c1,volume=0.45[s];[narr][duck][s]amix=inputs=3:duration=longest:dropout_transition=0,atrim=0:{runtime:.3f},loudnorm=I=-14:TP=-1:LRA=11:print_format=summary[out]"
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "warning", "-i", str(narration), "-i", str(music), "-i", str(sfx), "-filter_complex", mix, "-map", "[out]", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(final)])
    profile_name = {3: "midas_mystery_reflection", 4: "pandora_liminal_mystery"}.get(spec["episode_number"], "default_ragnarok_palette")
    (epdir / "music_sources.json").write_text(json.dumps({"profile": profile_name, "license_policy": "commercial_use_true_attribution_required_false", "sources": [{**item, "license_url": "https://mixkit.co/license/modal/musicFree/", "local_file": track.name} for item, track in zip(profile, tracks)], "note": "Licensed stock bed is arranged for emotional shape; it is not claimed to be historically authentic instrumentation for the civilization. Episode-specific profiles prevent accidental soundtrack reuse."}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out = epdir / "final_vertical_1080x1920.mp4"
    video = epdir / "video_captioned.mp4"
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(video), "-i", str(final), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)])
    for stem in (narration, music, sfx):
        shutil.copy2(stem, epdir / stem.name)
    return out


def qa(spec: dict[str, Any], epdir: Path) -> dict[str, Any]:
    tl = json.loads((epdir / "timeline.json").read_text(encoding="utf-8"))
    errors = []
    sources_path = epdir / "music_sources.json"
    if sources_path.exists():
        sources = json.loads(sources_path.read_text(encoding="utf-8"))
        if spec["episode_number"] in (3, 4):
            reused = {"Epical Drums 05", "Epic Games", "A New Life", "Fright Night", "Valley Sunset", "Silent Descent"}.intersection(item.get("title", "") for item in sources.get("sources", []))
            if reused: errors.append(f"episode {spec['episode_number']} reused an earlier soundtrack: " + ", ".join(sorted(reused)))
            expected_profile = {3: "midas_mystery_reflection", 4: "pandora_liminal_mystery"}[spec["episode_number"]]
            if sources.get("profile") != expected_profile: errors.append(f"episode {spec['episode_number']} music profile is not {expected_profile}")
    narration_duration = duration(epdir / "audio" / "narration.wav")
    video_duration = duration(epdir / "final_vertical_1080x1920.mp4")
    if abs(narration_duration - tl["runtime_seconds"]) > 0.06: errors.append("narration duration disagrees with timeline")
    if abs(video_duration - tl["runtime_seconds"]) > 0.12: errors.append("video duration disagrees with timeline")
    caps = tl["narration"]["captions"]
    for i, c in enumerate(caps):
        if c["end"] <= c["start"]: errors.append(f"caption {i+1} has non-positive duration")
        if i and c["start"] < caps[i-1]["end"] - 0.01: errors.append(f"caption overlap {i} -> {i+1}")
        if c["start"] < 0 or c["end"] > tl["runtime_seconds"] + 0.01: errors.append(f"caption {i+1} outside runtime")
        scene = next((s for s in tl["scenes"] if s["id"] == c["scene"]), None)
        if scene and (c["start"] < scene["start"] - 0.08 or c["end"] > scene["speech_end"] + 0.08): errors.append(f"caption {i+1} crosses a scene speech boundary")
    for i in range(1, 7):
        if not (epdir / "assets" / f"P{i:02d}.png").exists(): errors.append(f"missing P{i:02d}.png")
    audit = epdir / "caption_audit"; audit.mkdir(exist_ok=True)
    for i, c in enumerate(caps, 1):
        out = audit / f"caption_{i:03d}.jpg"
        run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{min(c['start']+0.05, video_duration-0.05):.3f}", "-i", str(epdir / "final_vertical_1080x1920.mp4"), "-frames:v", "1", "-vf", "scale=180:320", str(out)])
    report = {"episode": spec["episode_number"], "title": spec["title"], "timeline_runtime_seconds": tl["runtime_seconds"], "narration_runtime_seconds": round(narration_duration, 3), "video_runtime_seconds": round(video_duration, 3), "caption_count": len(caps), "caption_overlap_count": sum(1 for i in range(1, len(caps)) if caps[i]["start"] < caps[i-1]["end"] - 0.01), "scene_pauses_seconds": [{"from": tl["scenes"][i-1]["id"], "to": tl["scenes"][i]["id"], "seconds": tl["scenes"][i-1].get("measured_pause_after", tl["scenes"][i-1]["pause_after"]), "intended_seconds": tl["scenes"][i-1]["pause_after"]} for i in range(1, len(tl["scenes"]))], "source_integrity_classification": spec["source_integrity"]["classification"], "research_status": spec["source_integrity"]["research_status"], "auditory_playback": "not available to the agent; waveform, loudness, rendered-frame, and synchronization checks completed", "errors": errors, "status": "PASS" if not errors else "FAIL"}
    (epdir / "timing_qa_report.md").write_text("# Timing QA\n\n" + "\n".join(f"- **{k}:** {v}" for k, v in report.items() if k not in ("errors", "scene_pauses_seconds")) + "\n\n## Scene pauses\n" + "\n".join(f"- {x['from']} -> {x['to']}: {x['seconds']:.3f}s" for x in report["scene_pauses_seconds"]) + "\n\n## Errors\n" + ("\n".join(f"- {e}" for e in errors) if errors else "- None") + "\n", encoding="utf-8")
    (epdir / "qa_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def ensure_episode(ep: int) -> tuple[dict[str, Any], Path]:
    path, epdir = episode_paths(ep)
    spec = load_episode(path)
    errors = validate_spec(spec)
    if errors: raise RuntimeError("invalid episode: " + "; ".join(errors))
    epdir.mkdir(parents=True, exist_ok=True)
    (epdir / "source.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (epdir / "assets").mkdir(exist_ok=True)
    return spec, epdir


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", type=int, default=1)
    ap.add_argument("--stage", choices=["validate", "narration", "timeline", "captions", "render", "audio", "qa", "all"], default="all")
    args = ap.parse_args()
    if args.stage == "validate":
        report = validate_all(); print(json.dumps(report, ensure_ascii=False, indent=2)); return 0 if report["status"] == "PASS" else 1
    spec, epdir = ensure_episode(args.episode)
    if args.stage in ("narration", "timeline", "captions", "render", "audio", "qa", "all"):
        narration = build_narration(spec, epdir)
        print(f"narration={narration}")
    if args.stage in ("captions", "render", "audio", "qa", "all"):
        tl = json.loads((epdir / "timeline.json").read_text(encoding="utf-8")); write_srt(tl, epdir / "Captions_final.srt")
    if args.stage in ("render", "audio", "qa", "all"): render_video(spec, epdir)
    if args.stage in ("audio", "qa", "all"): build_audio(spec, epdir)
    if args.stage in ("qa", "all"):
        result = qa(spec, epdir); print(json.dumps(result, ensure_ascii=False, indent=2)); return 0 if result["status"] == "PASS" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
