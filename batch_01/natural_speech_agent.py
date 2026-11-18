"""Text and measured-timing review for narration-driven speech."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def inspect_episode(epdir: Path, timeline: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    policy = json.loads((Path(__file__).resolve().parents[1] / "production_feedback_gates.json").read_text(encoding="utf-8"))
    speech_policy = policy.get("word_timing", {})
    fail_gap = float(speech_policy.get("fail_internal_gap_seconds", 0.5))
    phrases = timeline.get("narration", {}).get("phrases", [])
    for previous, current in zip(phrases, phrases[1:]):
        gap = float(current.get("start", 0)) - float(previous.get("end", 0))
        previous_text = str(previous.get("text", "")).strip()
        if gap > fail_gap and previous_text and not re.search(r"[.!?]$", previous_text):
            findings.append({"type": "unnatural_internal_gap", "message": f"{gap:.3f}s gap after non-terminal phrase {previous_text!r}"})
    for cache_file in sorted((epdir / "audio").glob("scene_*_cache.json")):
        try:
            cache = json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            findings.append({"type": "unreadable_cache", "message": cache_file.name})
            continue
        spoken = str(cache.get("spoken_text", "")).strip()
        if not spoken:
            findings.append({"type": "empty_speech_cache", "message": cache_file.name})
        if re.search(r"\b([A-Za-z]+)\s+\1\b", spoken, re.IGNORECASE):
            findings.append({"type": "merged_or_repeated_word", "message": cache_file.name})
        if any(token in spoken for token in ("Ã", "â€™", "â€œ", "â€")):
            findings.append({"type": "encoding_error", "message": cache_file.name})
    return {"reviewer": "natural_speech_review", "status": "FAIL" if findings else "PASS", "findings": findings, "auditory_playback": "not available to automated gate"}
