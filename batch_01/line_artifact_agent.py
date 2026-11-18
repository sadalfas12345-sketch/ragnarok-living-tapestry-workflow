#!/usr/bin/env python3
"""Single-purpose reviewer for visible vertical panorama seams in encoded video."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

from .visual_gates_v2 import FFMPEG

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "production_feedback_gates.json").read_text(encoding="utf-8"))


def _frame(video: Path, timestamp: float) -> np.ndarray:
    p = subprocess.run([str(FFMPEG), "-v", "error", "-ss", f"{max(0.0, timestamp):.3f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=270:480,format=gray", "-f", "rawvideo", "pipe:1"], cwd=ROOT, check=True, capture_output=True)
    return np.frombuffer(p.stdout, dtype=np.uint8).reshape((480, 270)).astype(np.int16)


def inspect_video(video: Path, scenes: list[dict[str, Any]], runtime: float) -> dict[str, Any]:
    gate = POLICY.get("line_artifact_review", {})
    samples = []
    flagged = []
    interval = float(gate.get("sample_interval_seconds", 0.5))
    for scene in scenes:
        start, end = float(scene["start"]), float(scene["end"])
        timestamps = list(np.arange(start + 0.10, min(end, runtime - 0.05), interval))
        timestamps += [min(runtime - 0.05, end - 0.05)]
        for timestamp in sorted(set(round(float(x), 3) for x in timestamps if x > start and x < end)):
            gray = _frame(video, timestamp)
            edges = np.abs(np.diff(gray, axis=1))[:, 20:-20]
            means = edges.mean(axis=0)
            continuity = (edges > 32).mean(axis=0)
            score = means * continuity
            i = int(np.argmax(score))
            row = {"scene": scene["id"], "timestamp": round(timestamp, 3), "column": i + 20, "mean_edge": round(float(means[i]), 2), "continuity": round(float(continuity[i]), 3), "score": round(float(score[i]), 2)}
            samples.append(row)
            if row["mean_edge"] >= float(gate.get("max_mean_edge", 18.0)) and row["continuity"] >= float(gate.get("min_continuity", 0.06)):
                flagged.append(row)
    hard_gate = bool(gate.get("hard_gate", True))
    fail_on_any = bool(gate.get("fail_on_any_flagged_sample", True))
    failed = bool(flagged) if hard_gate and fail_on_any else bool(flagged)
    return {
        "reviewer": "line_artifact_agent",
        "scope": "visible intra-scene vertical joins and panorama seams only",
        "hard_gate": hard_gate,
        "status": "FAIL" if failed else "PASS",
        "samples": samples,
        "flagged_samples": flagged,
    }
