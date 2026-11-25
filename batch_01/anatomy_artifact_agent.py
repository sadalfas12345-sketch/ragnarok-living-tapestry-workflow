"""Hard gate for mutant-looking generated anatomy in rendered scenes.

This is intentionally review-backed: generic image heuristics cannot reliably
distinguish a hand from a prop or a deliberate crowd overlap. The gate requires
three sampled-frame verdicts per scene, with explicit PASS/FAIL notes from the
visual reviewer. Missing or incomplete review fails closed.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "production_feedback_gates.json").read_text(encoding="utf-8"))


def inspect_episode(epdir: Path, scenes: list[dict[str, Any]]) -> dict[str, Any]:
    policy = POLICY.get("anatomy_review", {})
    audit_path = epdir / "visual_gates_audit" / "anatomy_review.json"
    required = int(policy.get("required_samples_per_scene", 3))
    required_positions = tuple(policy.get("required_positions", ["opening", "middle", "ending"]))
    expected = {str(scene.get("id")) for scene in scenes}
    findings: list[dict[str, str]] = []
    samples: list[dict[str, Any]] = []
    asset_reviews: list[dict[str, Any]] = []
    crop_reviews: list[dict[str, Any]] = []

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
        asset_reviews = list(audit.get("asset_reviews", []))
        crop_reviews = list(audit.get("crop_reviews", []))
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
        if verdict != str(policy.get("required_verdict", "PASS")) and any(term in notes for term in policy.get("forbidden_findings", [])):
            findings.append({"type": "mutant_anatomy_detected", "scene": str(sample.get("scene")), "message": notes})
    for scene_id in sorted(expected):
        count = len(by_scene.get(scene_id, []))
        if count < required:
            findings.append({"type": "insufficient_anatomy_samples", "scene": scene_id, "message": f"{count}/{required} samples"})
        positions = {str(sample.get("position", "")) for sample in by_scene.get(scene_id, [])}
        for position in required_positions:
            if position not in positions:
                findings.append({"type": "missing_required_anatomy_position", "scene": scene_id, "message": position})

    if policy.get("require_source_asset_review", True):
        asset_dir = epdir / "assets"
        assets = sorted(asset_dir.glob("H*.png"))
        reviewed = {str(item.get("asset")): item for item in asset_reviews}
        if len(assets) < len(expected):
            findings.append({"type": "missing_source_assets", "message": f"{len(assets)}/{len(expected)} artwork assets found"})
        for asset in assets:
            item = reviewed.get(asset.name)
            if not item:
                findings.append({"type": "missing_source_asset_review", "asset": asset.name, "message": "full artwork review is required"})
                continue
            if str(item.get("status", "")).upper() != str(policy.get("required_verdict", "PASS")):
                findings.append({"type": "source_asset_verdict_not_pass", "asset": asset.name, "message": str(item.get("status", ""))})
            actual_hash = hashlib.sha256(asset.read_bytes()).hexdigest()
            if str(item.get("sha256", "")).lower() != actual_hash:
                findings.append({"type": "source_asset_hash_mismatch", "asset": asset.name, "message": "review evidence does not match current artwork"})
        if policy.get("require_overlapping_crop_review", True):
            for asset in assets:
                crops = [item for item in crop_reviews if str(item.get("asset")) == asset.name]
                if len(crops) < int(policy.get("minimum_crops_per_asset", 3)):
                    findings.append({"type": "insufficient_overlapping_crop_reviews", "asset": asset.name, "message": f"{len(crops)} reviews"})
                    continue
                ordered_crops = sorted(crops, key=lambda item: float(item.get("x_start", 2)))
                if float(ordered_crops[0].get("x_start", 2)) > 0.001 or float(ordered_crops[-1].get("x_end", -1)) < 0.999:
                    findings.append({"type": "crop_review_does_not_cover_full_asset", "asset": asset.name})
                for previous, current in zip(ordered_crops, ordered_crops[1:]):
                    if float(current.get("x_start", 2)) >= float(previous.get("x_end", -1)):
                        findings.append({"type": "crop_reviews_do_not_overlap", "asset": asset.name})
                for crop in ordered_crops:
                    if str(crop.get("status", "")).upper() != str(policy.get("required_verdict", "PASS")) or crop.get("boundary_reviewed") is not True:
                        findings.append({"type": "crop_review_not_pass", "asset": asset.name, "crop": crop.get("crop_id", "unknown")})
                    if str(crop.get("sha256", "")).lower() != hashlib.sha256(asset.read_bytes()).hexdigest():
                        findings.append({"type": "crop_review_hash_mismatch", "asset": asset.name, "crop": crop.get("crop_id", "unknown")})

    return {
        "reviewer": "anatomy_artifact_agent",
        "status": "FAIL" if findings else "PASS",
        "findings": findings,
        "samples": samples,
        "asset_reviews": asset_reviews,
        "crop_reviews": crop_reviews,
        "audit_path": str(audit_path),
    }
