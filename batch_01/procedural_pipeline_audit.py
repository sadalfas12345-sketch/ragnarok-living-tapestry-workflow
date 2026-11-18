"""Episode-agnostic production integrity reviewer."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def inspect_episode(epdir: Path, timeline: dict[str, Any], video: Path, srt: Path) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    source = epdir / "source.json"
    manifest = epdir / "audio" / "audio_manifest.json"
    if not source.exists():
        findings.append({"type": "missing_source", "message": "source.json is missing"})
    if not manifest.exists():
        findings.append({"type": "missing_audio_manifest", "message": "audio_manifest.json is missing"})
    scenes = timeline.get("scenes", [])
    if not scenes:
        findings.append({"type": "missing_scenes", "message": "timeline has no scenes"})
    for scene in scenes:
        asset = epdir / str(scene.get("asset", ""))
        if not asset.exists():
            findings.append({"type": "missing_asset", "scene": str(scene.get("id", "unknown")), "message": str(asset)})
    for path, label in ((video, "final video"), (srt, "captions")):
        if not path.exists() or path.stat().st_size == 0:
            findings.append({"type": "missing_output", "message": f"{label} is missing or empty"})
    if timeline.get("master_clock") != "audio/narration.wav":
        findings.append({"type": "wrong_master_clock", "message": "timeline master clock is not narration.wav"})
    return {"reviewer": "procedural_pipeline_audit", "status": "FAIL" if findings else "PASS", "findings": findings}
