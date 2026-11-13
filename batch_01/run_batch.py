#!/usr/bin/env python3
"""Resumable Batch 01 controller.

This controller never assumes that a missing visual asset is complete.  It
records a separate status file for every episode and only runs an episode when
the caller explicitly selects it.  Use --all only after the representative QA
pass has been accepted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source"
STATUS = ROOT / "status"
RUNNER = ROOT / "batch_runner.py"
STAGES = ["source_validation", "style_board", "scene_assets", "narration", "timeline", "captions", "render", "audio", "qa"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def source_for(ep: int) -> Path:
    matches = sorted(SOURCE.glob(f"{ep:02d}_*.json"))
    if len(matches) != 1:
        raise FileNotFoundError(f"expected one source file for episode {ep:02d}")
    return matches[0]


def read_status(ep: int) -> dict:
    STATUS.mkdir(exist_ok=True)
    path = STATUS / f"{ep:02d}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    src = source_for(ep)
    return {"episode": ep, "source_file": src.name, "source_sha256": hashlib.sha256(src.read_bytes()).hexdigest(), "updated_at": now(), "stages": {s: "PENDING" for s in STAGES}, "errors": []}


def write_status(data: dict) -> None:
    data["updated_at"] = now()
    path = STATUS / f"{data['episode']:02d}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def asset_state(ep: int) -> tuple[bool, bool]:
    try:
        spec = json.loads(source_for(ep).read_text(encoding="utf-8-sig"))
    except Exception:
        return False, False
    epdir = ROOT / "episodes" / f"{ep:02d}_{source_for(ep).stem[3:]}"
    style = (epdir / "references" / "style_board.png").exists()
    panels = all((epdir / "assets" / f"P{i:02d}.png").exists() for i in range(1, 7))
    return style, panels


def run_stage(ep: int, stage: str) -> None:
    cmd = [sys.executable, str(RUNNER), "--episode", str(ep), "--stage", stage]
    subprocess.run(cmd, cwd=ROOT.parent, check=True)


def refresh_asset_status(data: dict) -> None:
    style, panels = asset_state(data["episode"])
    data["stages"]["style_board"] = "PASS" if style else "BLOCKED_ASSET_REQUIRED"
    data["stages"]["scene_assets"] = "PASS" if panels else "BLOCKED_ASSET_REQUIRED"


def process(ep: int, requested: str, resume: bool) -> dict:
    data = read_status(ep)
    src = source_for(ep)
    current_hash = hashlib.sha256(src.read_bytes()).hexdigest()
    if data.get("source_sha256") != current_hash:
        data = {"episode": ep, "source_file": src.name, "source_sha256": current_hash, "updated_at": now(), "stages": {s: "PENDING" for s in STAGES}, "errors": ["source changed; cache invalidated"]}
    spec = json.loads(src.read_text(encoding="utf-8-sig"))
    required = ["schema_version", "title", "civilization", "source_integrity", "image_reference", "scenes"]
    data["stages"]["source_validation"] = "PASS" if all(k in spec for k in required) and len(spec.get("scenes", [])) == 6 else "FAIL"
    if data["stages"]["source_validation"] == "FAIL":
        data["errors"].append("source schema validation failed")
        write_status(data)
        raise RuntimeError(f"episode {ep:02d} source validation failed")
    refresh_asset_status(data)
    write_status(data)
    ordered = STAGES[3:] if requested == "all" else [requested]
    for stage in ordered:
        refresh_asset_status(data)
        if stage in ("style_board", "scene_assets"):
            if data["stages"][stage] != "PASS":
                data["stages"][stage] = "BLOCKED_ASSET_REQUIRED"
                write_status(data)
                if requested != "all": break
                raise RuntimeError(f"episode {ep:02d} requires {stage}")
            continue
        if resume and data["stages"].get(stage) == "PASS":
            continue
        try:
            run_stage(ep, stage)
            data["stages"][stage] = "PASS"
            data["errors"] = [e for e in data.get("errors", []) if not e.startswith(f"{stage}:")]
        except subprocess.CalledProcessError as exc:
            data["stages"][stage] = "FAIL"
            data["errors"].append(f"{stage}: exit {exc.returncode}")
            write_status(data)
            raise
        write_status(data)
    refresh_asset_status(data)
    write_status(data)
    return data


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", type=int)
    ap.add_argument("--all", action="store_true", help="run all episodes after their visual assets exist")
    ap.add_argument("--stage", choices=STAGES + ["all"], default="all")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()
    if args.status:
        for p in sorted(STATUS.glob("*.json")):
            print(p.read_text(encoding="utf-8"), end="")
        return 0
    if not args.all and args.episode is None:
        ap.error("select --episode N or explicitly pass --all")
    episodes = range(1, 31) if args.all else [args.episode]
    results = []
    for ep in episodes:
        try:
            results.append(process(ep, args.stage, args.resume))
        except Exception as exc:
            results.append({"episode": ep, "status": "FAILED", "error": str(exc)})
            if not args.all:
                print(json.dumps(results[-1], ensure_ascii=False, indent=2))
                return 1
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if all(x.get("stages", {}).get("qa") == "PASS" for x in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
