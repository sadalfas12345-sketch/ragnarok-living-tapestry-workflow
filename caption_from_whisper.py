from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
src = ROOT / "Captions_v15.srt"
dst = ROOT / "Captions_final.srt"

# Sentence onset timestamps measured from narration_woman_compact.wav with whisper.cpp.
starts = [0.000, 2.986, 5.972, 8.959, 11.946, 14.932, 17.919, 20.906,
          23.892, 26.879, 32.852, 35.839, 38.826, 41.346, 41.812,
          44.799, 47.786, 50.772, 53.759, 56.746, 59.732, 62.719,
          64.919, 65.706, 68.692, 74.479, 77.652]
ends = starts[1:] + [81.450]

def fmt(seconds):
    total = round(seconds * 1000)
    h, rem = divmod(total, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

blocks = re.split(r"\n\s*\n", src.read_text(encoding="utf-8").strip())
texts = []
for block in blocks:
    lines = block.splitlines()
    if len(lines) >= 3 and "-->" in lines[1]:
        texts.append(" ".join(lines[2:]).strip())
if len(texts) != len(starts):
    raise RuntimeError(f"Expected {len(starts)} captions, found {len(texts)}")

out = []
for idx, text in enumerate(texts):
    end = max(starts[idx] + 0.8, ends[idx] - 0.04)
    out.append(f"{idx + 1}\n{fmt(starts[idx])} --> {fmt(end)}\n{text}")
dst.write_text("\n\n".join(out) + "\n", encoding="utf-8")
print(dst)
