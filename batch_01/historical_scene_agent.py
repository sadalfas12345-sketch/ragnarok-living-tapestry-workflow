"""Independent historical scene-plausibility reviewer.

This is a contradiction detector, not a substitute for source scholarship.
Episodes can supply `historical_constraints` and `prohibited_visual_actions`
per scene; declared contradictions fail, while absent constraints are reported
for review instead of being silently treated as facts.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "production_feedback_gates.json").read_text(encoding="utf-8"))


def inspect_episode(source: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    unresolved = 0
    historical = str(source.get("source_integrity", {}).get("classification", "")).lower() == "historical_reconstruction_with_disputed_details"
    for index, scene in enumerate(source.get("scenes", []), 1):
        prompt = " ".join(str(scene.get(k, "")) for k in ("caption", "image_prompt", "required_visuals", "visual_progression")).lower()
        constraints = [str(x) for x in scene.get("historical_constraints", []) or []]
        prohibited = [str(x) for x in scene.get("prohibited_visual_actions", []) or []]
        if historical and not constraints and not prohibited:
            unresolved += 1
        for rule in constraints + prohibited:
            match = re.search(r"(?:forbid|prohibited|must not|never)\s*:\s*(.+)", rule, re.IGNORECASE)
            phrase = match.group(1).strip() if match else rule.strip()
            if phrase and phrase.lower() in prompt:
                findings.append({"scene": f"S{index:02d}", "type": "declared_contradiction", "message": f"visual direction contains prohibited historical action: {phrase}"})
    if unresolved:
        findings.append({"type": "needs_source_review", "message": f"{unresolved} historical scene(s) lack explicit historical constraints"})
    hard = bool(POLICY.get("historical_scene_review", {}).get("fail_on_declared_contradiction", True))
    failed = any(item["type"] == "declared_contradiction" for item in findings) and hard
    return {"reviewer": "historical_scene_agent", "status": "FAIL" if failed else ("REVIEW" if unresolved else "PASS"), "findings": findings}
