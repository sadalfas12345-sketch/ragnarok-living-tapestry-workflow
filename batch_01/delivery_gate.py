"""Fail-closed delivery gate for final video handoff."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate(epdir: Path, drive_url: str | None = None, drive_name: str | None = None, drive_sha256: str | None = None, allow_delivery_phase: bool = False) -> dict:
    video = epdir / "final_vertical_1080x1920.mp4"
    srt = epdir / "Captions_final.srt"
    qa_path = epdir / "qa_report.json"
    visual_path = epdir / "visual_gates_audit" / "visual_gates_report.json"
    lifecycle_path = epdir / "lifecycle_status.json"
    errors: list[str] = []

    for path in (video, srt, qa_path, visual_path, lifecycle_path):
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"missing delivery artifact: {path.name}")

    def read_json(path: Path, label: str) -> dict:
        if not path.is_file() or path.stat().st_size == 0:
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"{label} is unreadable: {exc}")
            return {}
        if not isinstance(value, dict):
            errors.append(f"{label} is not a JSON object")
            return {}
        return value

    qa = read_json(qa_path, "timing QA")
    visual = read_json(visual_path, "visual gates report")
    lifecycle = read_json(lifecycle_path, "lifecycle status")
    if qa.get("status") != "PASS":
        errors.append("timing QA is not PASS")
    if visual.get("status") != "PASS":
        errors.append("visual gates are not PASS")
    lifecycle_ok = lifecycle.get("status") == "complete" or (allow_delivery_phase and lifecycle.get("phase") == "delivery" and lifecycle.get("status") == "running")
    if not lifecycle_ok:
        errors.append("lifecycle is not complete")
    if not drive_url or not re.match(r"^https://drive\.google\.com/", drive_url):
        errors.append("Drive URL is missing")
    if not drive_name:
        errors.append("uploaded Drive filename is missing")
    local_hash = sha256(video) if video.exists() else None
    render_id = local_hash[:12] if local_hash else None
    expected_drive_name = f"{video.stem}_{render_id}{video.suffix}" if render_id else None
    if drive_name and render_id:
        # Descriptive filenames are allowed, but the short render hash must
        # remain in the filename so an older upload cannot be mistaken for
        # the current render.
        hash_marker = re.search(rf"(?i)(?:^|[_-]){re.escape(render_id)}(?:[_\.-]|$)", drive_name)
        if not hash_marker or not drive_name.lower().endswith(video.suffix.lower()):
            errors.append(f"Drive filename does not identify this render hash: {drive_name} must contain {render_id}")
    if not drive_sha256 or not re.fullmatch(r"[0-9a-fA-F]{64}", drive_sha256):
        errors.append("uploaded Drive SHA-256 is missing")
    elif local_hash != drive_sha256.lower():
        errors.append("uploaded Drive SHA-256 does not match the final local MP4")

    manifest = {
        "status": "PASS" if not errors else "FAIL",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "video": video.name,
        "video_sha256": local_hash,
        "render_id": render_id,
        "expected_drive_filename": expected_drive_name,
        "srt": srt.name,
        "qa": qa_path.name,
        "visual_gates": visual_path.name,
        "lifecycle": lifecycle_path.name,
        "drive_url": drive_url,
        "drive_filename": drive_name,
        "drive_sha256": drive_sha256,
        "errors": errors,
    }
    (epdir / "delivery_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode-dir", required=True)
    parser.add_argument("--drive-url")
    parser.add_argument("--drive-name")
    parser.add_argument("--drive-sha256")
    parser.add_argument("--allow-delivery-phase", action="store_true")
    args = parser.parse_args()
    result = validate(Path(args.episode_dir), args.drive_url, args.drive_name, args.drive_sha256, args.allow_delivery_phase)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
