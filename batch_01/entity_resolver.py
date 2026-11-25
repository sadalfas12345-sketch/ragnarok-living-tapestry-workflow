"""Detect and resolve likely proper names before script gates run.

The resolver is deterministic by default. An optional local LLM or lookup
endpoint can enrich unknown names without changing the authoritative script.
Unknown candidates are returned to the hard gate rather than guessed silently.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
CATALOG = json.loads((ROOT / "proper_name_catalog.json").read_text(encoding="utf-8-sig"))
PRONUNCIATIONS = json.loads((ROOT / "pronunciation_lexicon.json").read_text(encoding="utf-8-sig"))
INTRO_LEXICON = json.loads((ROOT / "character_intro_lexicon.json").read_text(encoding="utf-8-sig"))

COMMON_NON_NAMES = {
    "What", "If", "The", "A", "An", "In", "On", "At", "But", "And", "Then",
    "He", "She", "They", "It", "Few", "Other", "This", "That", "When", "While",
    "Either", "Later", "Every", "Their", "Yet", "Lord", "Lady", "General",
    "King", "Queen", "Prince", "Princess", "Official", "Captain", "Terrible",
    "Price", "Loyalty", "Ronin", "Forty-Seven",
    "After", "Before", "Only", "Some", "Many", "As", "For", "From", "By", "Into",
    "Greek", "Egyptian", "Maya", "Kiche", "K’iche’", "Athenian", "Cretan", "Bronze",
    "Age", "Mesopotamian", "Japanese", "Indian", "Chinese", "Roman", "English",
    "Irish", "Where", "Seasons", "Still", "Her", "One", "Help", "Death",
    "Epic", "Together", "Cedar", "Forest", "Days", "Terrified", "Even", "His", "Neither", "Creon's", "Without",
}


def _canonical_known_names() -> set[str]:
    return {str(x).casefold() for x in [*CATALOG.keys(), *PRONUNCIATIONS.keys(), *INTRO_LEXICON.keys()]}


def find_name_candidates(text: str) -> list[str]:
    """Find likely names, including a new capitalized creature or person."""
    candidates: list[str] = []
    known = _canonical_known_names()
    for name in [*CATALOG.keys(), *PRONUNCIATIONS.keys(), *INTRO_LEXICON.keys()]:
        if re.search(rf"\b{re.escape(str(name))}\b", text, re.IGNORECASE):
            candidates.append(str(name))
    # Mid-sentence capitalized words after an article or name-bearing verb are
    # likely entities such as "the Minotaur", even when absent from catalogs.
    pattern = r"\b(?:the|a|an|meets|confront|follows|sees|named|called|from)\s+([A-Z][\w’'À-ÖØ-öø-ÿ-]{2,}(?:\s+[A-Z][\w’'À-ÖØ-öø-ÿ-]{2,})?)"
    for match in re.finditer(pattern, text):
        candidate = match.group(1).strip(" ,.;:!?\"'”")
        if candidate in COMMON_NON_NAMES or candidate.casefold() in {x.casefold() for x in candidates}:
            continue
        if candidate.split()[0] in COMMON_NON_NAMES:
            continue
        candidates.append(candidate)
    return list(dict.fromkeys(candidates))


def resolve_unknown(name: str, context: str) -> dict[str, str] | None:
    """Resolve through a configured local LLM or lookup service.

    The endpoint must return JSON with `name`, `is_proper_name`, and optional
    `intro` and `pronunciation`. No network call is made unless explicitly
    configured by the workflow environment.
    """
    model = os.environ.get("LIVING_TAPESTRIES_LOCAL_LLM_MODEL", "qwen3.5:4b").strip()
    prompt = (
        "Return JSON only with keys is_proper_name, name, intro, pronunciation. "
        "Classify the capitalized term in context. is_proper_name must be false "
        "for ordinary adjectives, places used as adjectives, generic titles, "
        "or common nouns. If true, intro must be a spoiler-free role of at most "
        "six words.\nTERM: " + name + "\nCONTEXT: " + context
    )
    if os.environ.get("LIVING_TAPESTRIES_DISABLE_LOCAL_LLM", "").lower() not in {"1", "true", "yes"}:
        try:
            completed = subprocess.run(
                ["ollama", "run", model, "--format", "json", "--think=false", "--hidethinking", prompt],
                check=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=8,
            )
            result = json.loads(completed.stdout.strip())
            if isinstance(result, dict) and isinstance(result.get("response"), str):
                result = json.loads(result["response"])
            if isinstance(result, dict):
                return {k: str(result[k]) for k in ("name", "intro", "pronunciation", "is_proper_name") if k in result}
        except Exception:
            pass
    endpoint = os.environ.get("LIVING_TAPESTRIES_LOCAL_LLM_URL", "").strip()
    if not endpoint:
        endpoint = os.environ.get("LIVING_TAPESTRIES_ENTITY_LOOKUP_URL", "").strip()
    if not endpoint:
        return None
    payload = json.dumps({
        "instruction": "Identify whether this capitalized term is a named person, creature, deity, place, or title. If so, provide a short spoiler-free role intro of at most six words and a pronunciation. Return JSON only.",
        "name": name,
        "context": context,
    }).encode("utf-8")
    try:
        request = Request(endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=8) as response:
            result = json.loads(response.read().decode("utf-8"))
        if isinstance(result, dict) and result.get("is_proper_name"):
            return {k: str(result[k]) for k in ("name", "intro", "pronunciation") if k in result}
    except Exception:
        return None
    return None


def audit_text(text: str) -> list[dict[str, str]]:
    """Resolve every likely unknown name and return hard-gate findings."""
    known = _canonical_known_names()
    findings: list[dict[str, str]] = []
    for candidate in find_name_candidates(text):
        if candidate.casefold() in known or candidate.rstrip("s").casefold() in known:
            continue
        match = re.search(rf"\b{re.escape(candidate)}\b", text, re.IGNORECASE)
        if match:
            left = text.rfind(".", 0, match.start()) + 1
            right = text.find(".", match.end())
            context = text[left:(len(text) if right < 0 else right + 1)].strip()
        else:
            context = text
        # Never silently skip an unknown capitalized entity. The resolver may
        # classify it as an ordinary word or a place, but that decision must
        # come from the configured local reviewer rather than a heuristic.
        resolved = resolve_unknown(candidate, context)
        if not resolved:
            findings.append({"name": candidate, "context": context, "reason": "no local resolver result"})
        elif str(resolved.get("is_proper_name", "")).lower() not in {"true", "1", "yes"}:
            continue
    return findings


# Expansion-schema name discovery.  Keep this after the legacy function so
# older episode behavior remains intact while unlisted names are still sent
# through the resolver instead of requiring manual catalog insertion.
_legacy_find_name_candidates = find_name_candidates


def find_name_candidates_expanded(text: str) -> list[str]:
    candidates = _legacy_find_name_candidates(text)
    patterns = (
        r"\b(?:Lord|Lady|General|King|Queen|Prince|Princess|Official|Captain)\s+([A-Z][A-Za-z'-]{2,})",
        r"\b(?:attacked|challenged|followed|carried|ordered|met|killed)\s+([A-Z][A-Za-z'-]{2,})",
        r"(?<![.!?])\b([A-Z][A-Za-z'-]{2,})\b",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            candidate = match.group(1).strip("'\"")
            if candidate not in COMMON_NON_NAMES and candidate.casefold() not in {x.casefold() for x in candidates}:
                candidates.append(candidate)
    return list(dict.fromkeys(candidates))


find_name_candidates = find_name_candidates_expanded


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the pre-render likely-name resolution gate.")
    parser.add_argument("source", type=Path, help="authoritative episode JSON")
    args = parser.parse_args()
    source = json.loads(args.source.read_text(encoding="utf-8-sig"))
    text = " ".join(str(scene.get("caption", "")) for scene in source.get("scenes", []))
    findings = audit_text(text)
    print(json.dumps({"status": "FAIL" if findings else "PASS", "findings": findings}, ensure_ascii=False, indent=2))
    raise SystemExit(1 if findings else 0)
