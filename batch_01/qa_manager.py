"""Checklist gate that prevents partial QA from being reported as complete."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from batch_01.batch_runner import validate_spec
from batch_01.entity_resolver import audit_text
from batch_01.historical_scene_agent import inspect_episode as historical_gate
from batch_01.name_spelling_agent import inspect_episode as name_gate
from batch_01.music_gate import validate as music_gate


REQUIRED_GATES = (
    "schema",
    "entity_resolution",
    "name_spelling",
    "historical_scene",
    "what_if_hook",
    "caption_source",
    "visual_content",
    "timing",
    "audio",
    "music_license_and_presence",
    "delivery",
)


def load_episode(path: Path, slug: str | None) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, dict) and isinstance(payload.get("episodes"), list):
        if not slug:
            raise ValueError("package input requires --slug")
        payload = next((item for item in payload["episodes"] if item.get("slug") == slug), None)
        if payload is None:
            raise ValueError(f"episode not found: {slug}")
    if not isinstance(payload, dict) or not isinstance(payload.get("scenes"), list):
        raise ValueError("input is not an episode JSON")
    return payload


def run(source: dict[str, Any], artifact_dir: Path | None = None) -> dict[str, Any]:
    captions = " ".join(str(scene.get("caption", "")) for scene in source["scenes"])
    results: dict[str, dict[str, Any]] = {
        "schema": {"status": "PASS" if not validate_spec(source) else "FAIL", "errors": validate_spec(source)},
        "entity_resolution": {"status": "PASS" if not audit_text(captions) else "FAIL", "findings": audit_text(captions)},
        "name_spelling": name_gate(source, captions),
        "historical_scene": historical_gate(source),
        "what_if_hook": {"status": "PASS" if captions.lstrip().lower().startswith("what if") else "FAIL"},
        "caption_source": {"status": "PASS" if all(str(s.get("caption", "")).strip() for s in source["scenes"]) else "FAIL"},
    }
    if artifact_dir:
        for key, filename in (("visual_content", "visual_gates_audit/visual_gates_report.json"), ("timing", "qa_report.json"), ("audio", "audio/audio_manifest.json"), ("delivery", "delivery_manifest.json")):
            path = artifact_dir / filename
            if not path.exists():
                results[key] = {"status": "MISSING", "file": str(path)}
            else:
                try:
                    data = json.loads(path.read_text(encoding="utf-8-sig"))
                    status = str(data.get("status", "")).upper()
                    if key == "audio" and not status and data.get("final_video_duration_seconds"):
                        status = "PASS"
                    results[key] = {"status": status or "UNKNOWN", "file": str(path)}
                except Exception as exc:
                    results[key] = {"status": "FAIL", "file": str(path), "error": str(exc)}
        music_result = music_gate(artifact_dir)
        results["music_license_and_presence"] = {
            "status": music_result["status"],
            "checks": music_result.get("checks", {}),
            "errors": music_result.get("errors", []),
        }
    else:
        for key in ("visual_content", "timing", "audio", "music_license_and_presence", "delivery"):
            results[key] = {"status": "MISSING", "reason": "no rendered artifact directory supplied"}
    failed = [key for key, value in results.items() if value.get("status") != "PASS"]
    return {"episode": source.get("episode_number"), "slug": source.get("slug"), "required_gates": list(REQUIRED_GATES), "gates": results, "status": "PASS" if not failed else "FAIL", "blocking_gates": failed}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--slug")
    parser.add_argument("--artifact-dir", type=Path)
    args = parser.parse_args()
    report = run(load_episode(args.source, args.slug), args.artifact_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
