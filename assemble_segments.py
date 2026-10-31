"""Compatibility entry point. The authoritative renderer consumes timeline.json."""
from pathlib import Path
import subprocess, sys
ROOT = Path(__file__).resolve().parent
subprocess.run([sys.executable, str(ROOT / "render_from_timeline.py")], check=True)
