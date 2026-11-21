"""Independent anti-awkward-wording reviewer and safe smoothing pass."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "production_feedback_gates.json").read_text(encoding="utf-8"))


def smooth_gate_insertions(text: str) -> str:
    """Apply only safe mechanical repairs before TTS; never rewrite story facts."""
    text = re.sub(r"\b([A-Za-z]+)([,.!?]?)\s+\1\b", r"\1\2", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(\d{4})\s+tradition\b", r"the tradition of \1", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(In\s+[^,.!?]+),\s*\1\b", r"\1", text, flags=re.IGNORECASE)
    return re.sub(r"\s+([,.!?])", r"\1", text).strip()


def inspect_episode(source: dict[str, Any], caption_text: str) -> dict[str, Any]:
    policy = POLICY.get("wording_review", {})
    findings: list[dict[str, str]] = []
    words = re.findall(r"\b[A-Za-z][A-Za-z'’-]*\b", caption_text.lower())
    for a, b in zip(words, words[1:]):
        if a == b:
            findings.append({"type": "duplicate_word", "text": a, "message": f"repeated word {a!r}"})
    for year in sorted(set(re.findall(r"\b(?:1[0-9]{3}|20[0-9]{2})\b", caption_text))):
        if len(re.findall(rf"\b{year}\b", caption_text)) > int(policy.get("max_year_repeats", 1)):
            findings.append({"type": "repeated_date", "text": year, "message": f"date {year} is repeated without an explicit narrative reason"})
    civilization = str(source.get("civilization", "")).strip()
    labels = [x.strip() for x in re.split(r"\s+and\s+|,", civilization) if len(x.strip()) > 3 and re.search(r"[A-Za-z]", x)]
    for label in labels:
        count = len(re.findall(rf"\b{re.escape(label)}\b", caption_text, re.IGNORECASE))
        if count > int(policy.get("max_civilization_label_repeats", 1)):
            findings.append({"type": "repeated_civilization_label", "text": label, "message": f"civilization label {label!r} is repeated"})
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", caption_text) if s.strip()]
    for previous, current in zip(sentences, sentences[1:]):
        if previous.lower() == current.lower():
            findings.append({"type": "duplicate_sentence", "text": current, "message": "adjacent sentence repeated"})
        if re.match(r"^(and|but|so|then)\b", current, re.IGNORECASE) and len(current.split()) <= 4:
            findings.append({"type": "awkward_join", "text": current, "message": "short conjunction fragment may be an awkward gate insertion"})
    for item in policy.get("awkward_phrase_patterns", []):
        pattern = str(item.get("pattern", ""))
        if pattern and re.search(pattern, caption_text, re.IGNORECASE | re.DOTALL):
            findings.append({
                "type": "awkward_phrase",
                "text": pattern,
                "message": str(item.get("message", "awkward phrase pattern detected")),
            })
    plainspoken = policy.get("plainspoken_language_gate", {})
    if plainspoken.get("enabled"):
        for item in plainspoken.get("patterns", []):
            pattern = str(item.get("pattern", ""))
            if pattern and re.search(pattern, caption_text, re.IGNORECASE | re.DOTALL):
                findings.append({
                    "type": "bureaucratic_language",
                    "text": pattern,
                    "message": str(item.get("message", "rewrite in direct spoken language")),
                })
    hard = bool(policy.get("fail_on_findings", True))
    return {"reviewer": "wording_agent", "status": "FAIL" if findings and hard else ("REVIEW" if findings else "PASS"), "findings": findings}
