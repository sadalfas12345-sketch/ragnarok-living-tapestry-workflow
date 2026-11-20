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
NAME_CATALOG = json.loads((ROOT / "batch_01" / "proper_name_catalog.json").read_text(encoding="utf-8"))


def _source_text(source: dict[str, Any]) -> str:
    spoken: dict[str, Any] = {
        "title": source.get("title", ""),
        "opening_hook": source.get("opening_hook", ""),
        "proper_names": source.get("proper_names", []),
        "scenes": [
            {
                key: scene.get(key, "")
                for key in ("caption", "narration", "spoken_text", "script")
                if scene.get(key)
            }
            for scene in source.get("scenes", [])
        ],
    }
    return json.dumps(spoken, ensure_ascii=False)


def inspect_episode(source: dict[str, Any], caption_text: str) -> dict[str, Any]:
    policy = POLICY.get("name_spelling_review", {})
    pronunciation_policy = POLICY.get("proper_name_pronunciation_gate", {})
    source_text = _source_text(source)
    findings: list[dict[str, str]] = []
    names: list[str] = []
    names.extend(str(x) for x in source.get("proper_names", []) or [])
    for name in NAME_CATALOG:
        if re.search(rf"\b{re.escape(name)}\b", source_text, re.IGNORECASE):
            names.append(name)
    # Character design locks are visual metadata, not required narration text.
    # Only names present in authoritative prose or the pronunciation lexicon
    # are required to survive into the final captions.
    for name in LEXICON:
        if re.search(rf"\b{re.escape(name)}\b", source_text, re.IGNORECASE):
            names.append(name)
    identified_names: list[dict[str, str]] = []
    for name in dict.fromkeys(n for n in names if len(n.strip()) >= 3):
        aliases = policy.get("accepted_aliases", {}).get(name, [])
        present = re.search(rf"\b{re.escape(name)}\b", caption_text, re.IGNORECASE) or any(re.search(rf"\b{re.escape(str(alias))}\b", caption_text, re.IGNORECASE) for alias in aliases)
        if " " in name and name[0].islower():
            continue
        if re.search(rf"\b{re.escape(name)}\b", source_text, re.IGNORECASE) and not present:
            findings.append({"type": "missing_or_changed_name", "name": name, "message": f"authoritative name {name!r} is absent or changed in final captions"})
        if pronunciation_policy.get("enabled", True):
            lexicon_key = next((key for key in LEXICON if key.casefold() == name.casefold()), None)
            if lexicon_key:
                identified_names.append({"name": name, "mode": "native_lexicon", "pronunciation": str(LEXICON[lexicon_key])})
            elif pronunciation_policy.get("allow_english_source_spelling_fallback", True):
                identified_names.append({"name": name, "mode": "english_source_spelling_fallback", "pronunciation": name})
            else:
                findings.append({"type": "missing_pronunciation", "name": name, "message": f"no native pronunciation is available for {name!r} and English fallback is disabled"})
    for canonical, variants in policy.get("common_misspellings", {}).items():
        for variant in variants:
            if re.search(rf"\b{re.escape(str(variant))}\b", caption_text, re.IGNORECASE):
                findings.append({"type": "misspelling", "name": str(variant), "expected": str(canonical), "message": f"use {canonical!r}, not {variant!r}"})
    return {"reviewer": "name_spelling_agent", "status": "FAIL" if findings else "PASS", "identified_names": identified_names, "findings": findings}
