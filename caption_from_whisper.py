"""Legacy name retained for callers. The sentence-level timeline is authoritative."""
from pathlib import Path
import subprocess, sys
ROOT = Path(__file__).resolve().parent
subprocess.run([sys.executable, str(ROOT / "build_srt_from_timeline.py")], check=True)
