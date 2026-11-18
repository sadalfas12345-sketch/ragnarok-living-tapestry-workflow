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
    for scene in scenes:
        start, end = float(scene["start"]), float(scene["end"])
        for fraction in gate.get("sample_fractions", [0.2, 0.5, 0.8]):
            timestamp = min(runtime - 0.05, start + (end - start) * float(fraction))
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
    return {"reviewer": "line_artifact_agent", "scope": "visible vertical panorama seams only", "status": "FAIL" if flagged else "PASS", "samples": samples, "flagged_samples": flagged}
