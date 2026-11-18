"""Independent hostile review of encoded frames and scene boundaries."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .visual_gates_v2 import frame_bytes, mean_abs_diff


def inspect_episode(video: Path, scenes: list[dict[str, Any]]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    for scene in scenes:
        start, end = float(scene["start"]), float(scene["end"])
        samples = [frame_bytes(video, start + (end - start) * fraction) for fraction in (0.08, 0.50, 0.92)]
        luma = [sum(frame) / max(1, len(frame)) for frame in samples]
        changes = [mean_abs_diff(samples[i], samples[i + 1]) for i in range(2)]
        if min(luma, default=0) < 3.0:
            findings.append({"type": "near_black_scene_frame", "scene": str(scene.get("id")), "message": f"luma={luma}"})
        if max(changes, default=0) < 0.35:
            findings.append({"type": "static_scene", "scene": str(scene.get("id")), "message": f"frame_diffs={changes}"})
    for left, right in zip(scenes, scenes[1:]):
        boundary = float(right["start"])
        before = frame_bytes(video, boundary - 0.06)
        after = frame_bytes(video, boundary + 0.14)
        if sum(after) / max(1, len(after)) < 3.0:
            findings.append({"type": "black_transition_frame", "scene": str(right.get("id")), "message": "incoming scene is near black"})
        if mean_abs_diff(before, after) < 0.05:
            findings.append({"type": "frozen_transition", "scene": str(right.get("id")), "message": "boundary shows no visible progression"})
    return {"reviewer": "adversarial_render_review", "status": "FAIL" if findings else "PASS", "findings": findings}
