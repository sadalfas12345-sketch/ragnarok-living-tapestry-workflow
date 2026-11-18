"""Independent proper-name spelling reviewer.

The source JSON and pronunciation lexicon are authoritative. This reviewer
checks the final caption text after all gate insertions and never rewrites a
name silently.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "production_feedback_gates.json").read_text(encoding="utf-8"))
LEXICON = json.loads((ROOT / "batch_01" / "pronunciation_lexicon.json").read_text(encoding="utf-8"))


def _source_text(source: dict[str, Any]) -> str:
    return json.dumps(source, ensure_ascii=False)


def inspect_episode(source: dict[str, Any], caption_text: str) -> dict[str, Any]:
    policy = POLICY.get("name_spelling_review", {})
    source_text = _source_text(source)
    findings: list[dict[str, str]] = []
    names: list[str] = []
    names.extend(str(x) for x in source.get("proper_names", []) or [])
    names.extend(str(x) for x in source.get("image_reference", {}).get("character_design_lock", []) or [])
    for name in LEXICON:
        if re.search(rf"\b{re.escape(name)}\b", source_text, re.IGNORECASE):
            names.append(name)
    for name in dict.fromkeys(n for n in names if len(n.strip()) >= 3):
        aliases = policy.get("accepted_aliases", {}).get(name, [])
        present = re.search(rf"\b{re.escape(name)}\b", caption_text, re.IGNORECASE) or any(re.search(rf"\b{re.escape(str(alias))}\b", caption_text, re.IGNORECASE) for alias in aliases)
        if " " in name and name[0].islower():
            continue
        if re.search(rf"\b{re.escape(name)}\b", source_text, re.IGNORECASE) and not present:
            findings.append({"type": "missing_or_changed_name", "name": name, "message": f"authoritative name {name!r} is absent or changed in final captions"})
    for canonical, variants in policy.get("common_misspellings", {}).items():
        for variant in variants:
            if re.search(rf"\b{re.escape(str(variant))}\b", caption_text, re.IGNORECASE):
                findings.append({"type": "misspelling", "name": str(variant), "expected": str(canonical), "message": f"use {canonical!r}, not {variant!r}"})
    return {"reviewer": "name_spelling_agent", "status": "FAIL" if findings else "PASS", "findings": findings}
