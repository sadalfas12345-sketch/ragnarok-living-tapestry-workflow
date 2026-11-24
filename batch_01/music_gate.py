"""Hard gate for culturally appropriate, licensed, audible soundtrack beds."""
from __future__ import annotations

import hashlib
import json
import wave
from pathlib import Path
from typing import Any

import numpy as np

POLICY = json.loads((Path(__file__).resolve().parents[1] / "production_feedback_gates.json").read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _duration(path: Path) -> float:
    with wave.open(str(path), "rb") as fh:
        return fh.getnframes() / float(fh.getframerate())


def _audible(path: Path) -> dict[str, float | bool]:
    with wave.open(str(path), "rb") as fh:
        frames = fh.readframes(fh.getnframes())
        channels = fh.getnchannels()
        sample_width = fh.getsampwidth()
    if sample_width != 2:
        return {"audible": False, "rms": 0.0, "peak": 0.0}
    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    rms = float(np.sqrt(np.mean(audio * audio))) if audio.size else 0.0
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    return {"audible": rms >= 0.001 and peak >= 0.01, "rms": round(rms, 6), "peak": round(peak, 6)}


def validate(artifact_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    source_path = artifact_dir / "music_sources.json"
    audio_path = artifact_dir / "audio" / "audio_manifest.json"
    stem_path = artifact_dir / "audio" / "music_stem.wav"
    result: dict[str, Any] = {"gate": "music_license_and_presence", "checks": {}, "errors": errors}

    if not source_path.exists():
        errors.append("music_sources.json is missing")
        return {**result, "status": "FAIL"}
    try:
        source = json.loads(source_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        errors.append(f"music_sources.json is invalid: {exc}")
        return {**result, "status": "FAIL"}

    sources = source.get("sources")
    music_policy = POLICY.get("music", {})
    story_path = artifact_dir / "source.json"
    story = {}
    if story_path.exists():
        try:
            story = json.loads(story_path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            errors.append(f"source.json is unreadable for soundtrack-fit validation: {exc}")
    story_audio = story.get("audio", {}) if isinstance(story, dict) else {}
    direction = str(story_audio.get("soundtrack_direction", "")).strip()
    profile = str(source.get("profile", "")).strip()
    result["checks"]["profile"] = profile
    result["checks"]["json_soundtrack_direction"] = direction
    if music_policy.get("require_episode_specific_profile"):
        rejected = {str(x).lower() for x in music_policy.get("reject_generic_fallback_profiles", [])}
        if not profile or profile.lower() in rejected:
            errors.append(f"soundtrack profile is generic or missing: {profile or '<missing>'}")
        if not source.get("episode_specific_profile"):
            errors.append("music_sources.json does not prove an episode-specific profile")
    if music_policy.get("require_json_direction_evidence"):
        if not direction:
            errors.append("authoritative JSON has no soundtrack_direction")
        if not source.get("soundtrack_direction"):
            errors.append("music_sources.json does not preserve soundtrack_direction evidence")
        elif str(source.get("soundtrack_direction")).strip().lower() != direction.lower():
            errors.append("music_sources.json soundtrack_direction disagrees with source.json")
        if not source.get("selection_rationale"):
            errors.append("music_sources.json is missing selection_rationale")
    if music_policy.get("require_scene_cue_coverage"):
        expected_cues = [scene.get("music", {}) for scene in story.get("scenes", []) if isinstance(scene, dict)]
        actual_cues = source.get("scene_cues", [])
        if len(actual_cues) < len(expected_cues):
            errors.append(f"music_sources.json covers {len(actual_cues)} scene cues but JSON declares {len(expected_cues)}")
        for index, expected in enumerate(expected_cues):
            if index >= len(actual_cues):
                break
            actual = actual_cues[index]
            if str(actual.get("cue", "")) != str(expected.get("cue", "")) or str(actual.get("instrumentation", "")) != str(expected.get("instrumentation", "")):
                errors.append(f"scene cue {index + 1:02d} does not match authoritative JSON")
    if not isinstance(sources, list) or not sources:
        errors.append("music source list is empty")
    result["checks"]["source_count"] = len(sources) if isinstance(sources, list) else 0
    result["checks"]["license_policy"] = source.get("license_policy")

    for index, item in enumerate(sources or [], start=1):
        label = f"source_{index}"
        required = ("title", "artist", "url", "license_url", "local_file")
        missing = [key for key in required if not item.get(key)]
        if missing:
            errors.append(f"{label} missing fields: {', '.join(missing)}")
        if item.get("commercial_use") is not True:
            errors.append(f"{label} does not explicitly allow commercial use")
        if item.get("attribution_required") is not False:
            errors.append(f"{label} is not verified attribution-free")
        if item.get("tiktok_use") is not True:
            errors.append(f"{label} is not verified for TikTok use")
        if item.get("content_id_registration") is not False:
            errors.append(f"{label} has no explicit prohibition on Content ID registration")
        local = artifact_dir / "audio" / str(item.get("local_file", ""))
        if not local.exists():
            errors.append(f"{label} local audio is missing: {local.name}")
        elif item.get("sha256") and _sha256(local).lower() != str(item["sha256"]).lower():
            errors.append(f"{label} local audio SHA-256 does not match the evidence")

    if not audio_path.exists():
        errors.append("audio/audio_manifest.json is missing")
    else:
        audio = json.loads(audio_path.read_text(encoding="utf-8-sig"))
        result["checks"]["runtime_seconds"] = audio.get("runtime_seconds")
        if audio.get("music_sha256") and stem_path.exists() and _sha256(stem_path).lower() != str(audio["music_sha256"]).lower():
            errors.append("audio manifest music SHA-256 does not match music_stem.wav")

    if not stem_path.exists():
        errors.append("audio/music_stem.wav is missing")
    else:
        duration = round(_duration(stem_path), 3)
        result["checks"]["music_stem_duration_seconds"] = duration
        runtime = float(result["checks"].get("runtime_seconds") or 0)
        if runtime and abs(duration - runtime) > 0.12:
            errors.append(f"music stem duration {duration}s does not match runtime {runtime}s")
        presence = _audible(stem_path)
        result["checks"]["music_presence"] = presence
        if not presence["audible"]:
            errors.append("music stem is effectively silent")

    result["status"] = "PASS" if not errors else "FAIL"
    return result
