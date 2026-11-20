"""Lifecycle heartbeat and fail-closed status reporting for long renders."""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Lifecycle:
    def __init__(self, epdir: Path, episode: int, interval: int = 60) -> None:
        self.epdir = epdir
        self.episode = episode
        self.interval = max(5, interval)
        self.status_path = epdir / "lifecycle_status.json"
        self._phase = "starting"
        self._status = "running"
        self._output: Path | None = None
        self._started = time.time()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _write(self, *, error: str | None = None) -> None:
        output_bytes = self._output.stat().st_size if self._output and self._output.exists() else 0
        payload: dict[str, Any] = {
            "episode": self.episode,
            "phase": self._phase,
            "status": self._status,
            "pid": os.getpid(),
            "last_heartbeat": datetime.now(timezone.utc).isoformat(),
            "output_file": str(self._output) if self._output else None,
            "output_bytes": output_bytes,
            "elapsed_seconds": round(time.time() - self._started, 3),
        }
        if error:
            payload["error"] = error
        self.epdir.mkdir(parents=True, exist_ok=True)
        self.status_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _heartbeat(self) -> None:
        while not self._stop.wait(self.interval):
            self._write()

    def start(self) -> None:
        self._status = "running"
        self._write()
        self._thread = threading.Thread(target=self._heartbeat, name=f"lifecycle-{self.episode}", daemon=True)
        self._thread.start()

    def phase(self, name: str, output: Path | None = None) -> None:
        self._phase = name
        if output is not None:
            self._output = output
        self._write()

    def complete(self) -> None:
        self._phase = "complete"
        self._status = "complete"
        self._write()
        self._stop.set()

    def fail(self, error: BaseException | str) -> None:
        self._phase = "failed"
        self._status = "failed"
        self._write(error=str(error))
        self._stop.set()

