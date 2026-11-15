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
            if travel_rate > POLICY["camera"]["max_normalized_travel_per_second"]:
                errors.append(f"scene {scene['id']} camera travel is too fast: {travel_rate:.3f} normalized units/sec")
        camera = scene.get("camera", {})
        if POLICY["camera"]["forbid_shake"] and camera.get("no_shake") is not True:
            errors.append(f"scene {scene['id']} does not explicitly forbid camera shake")
        if POLICY["camera"]["forbid_hard_crop_changes"] and camera.get("no_hard_crop_changes") is not True:
            errors.append(f"scene {scene['id']} does not explicitly forbid hard crop changes")
        previous_end = end
    if scenes and abs(previous_end - runtime) > 0.12: errors.append("last scene end disagrees with timeline runtime")

    captions = parse_srt(srt)
    for i, cap in enumerate(captions):
        if cap["end"] <= cap["start"]: errors.append(f"caption {i + 1} has non-positive duration")
        if cap["start"] < -0.01 or cap["end"] > runtime + 0.12: errors.append(f"caption {i + 1} is outside the timeline")
        if i and cap["start"] < captions[i - 1]["end"] - 0.001: errors.append(f"caption overlap {i} -> {i + 1}")

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

    report = {
        "episode": epdir.name, "status": "PASS" if not errors else "FAIL", "errors": errors,
        "warnings": warnings, "timeline_runtime_seconds": runtime, "video_runtime_seconds": round(actual_runtime, 3),
        "dimensions": [width, height], "video_bitrate": bitrate, "caption_count": len(captions),
        "scene_visual_audit": scene_audit, "transition_audit": transition_audit,
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
