"""Hard gate for mutant-looking generated anatomy in rendered scenes.

This is intentionally review-backed: generic image heuristics cannot reliably
distinguish a hand from a prop or a deliberate crowd overlap. The gate requires
three sampled-frame verdicts per scene, with explicit PASS/FAIL notes from the
visual reviewer. Missing or incomplete review fails closed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "production_feedback_gates.json").read_text(encoding="utf-8"))


def inspect_episode(epdir: Path, scenes: list[dict[str, Any]]) -> dict[str, Any]:
    policy = POLICY.get("anatomy_review", {})
    audit_path = epdir / "visual_gates_audit" / "anatomy_review.json"
    required = int(policy.get("required_samples_per_scene", 3))
    expected = {str(scene.get("id")) for scene in scenes}
    findings: list[dict[str, str]] = []
    samples: list[dict[str, Any]] = []

    if not audit_path.exists():
        return {
            "reviewer": "anatomy_artifact_agent",
            "status": "FAIL",
            "findings": [{"type": "missing_anatomy_review", "message": str(audit_path)}],
            "samples": [],
        }
    try:
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        samples = list(audit.get("samples", []))
    except Exception as exc:
        return {
            "reviewer": "anatomy_artifact_agent",
            "status": "FAIL",
            "findings": [{"type": "unreadable_anatomy_review", "message": str(exc)}],
            "samples": [],
        }

    by_scene: dict[str, list[dict[str, Any]]] = {}
    for sample in samples:
        by_scene.setdefault(str(sample.get("scene")), []).append(sample)
        verdict = str(sample.get("verdict", "")).upper()
        notes = str(sample.get("notes", "")).lower()
        if verdict != str(policy.get("required_verdict", "PASS")):
            findings.append({"type": "anatomy_verdict_not_pass", "scene": str(sample.get("scene")), "message": verdict or "missing verdict"})
        if any(term in notes for term in policy.get("forbidden_findings", [])):
            findings.append({"type": "mutant_anatomy_detected", "scene": str(sample.get("scene")), "message": notes})
    for scene_id in sorted(expected):
        count = len(by_scene.get(scene_id, []))
        if count < required:
            findings.append({"type": "insufficient_anatomy_samples", "scene": scene_id, "message": f"{count}/{required} samples"})

    return {
        "reviewer": "anatomy_artifact_agent",
        "status": "FAIL" if findings else "PASS",
        "findings": findings,
        "samples": samples,
        "audit_path": str(audit_path),
    }
