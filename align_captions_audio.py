from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
src = ROOT / "Captions_v15.srt"
dst = ROOT / "Captions_v18.srt"

scene_starts = [0.000, 7.260, 15.400, 23.440, 32.540, 40.720, 47.700, 56.770, 64.120, 73.230]
scene_ends = [7.260, 15.400, 23.440, 32.540, 40.720, 47.700, 56.770, 64.120, 73.230, 80.280]

# Sentence onset estimates read from the actual generated woman-narration waveforms.
# They use the end of the natural inter-sentence pause, rather than proportional text timing.
relative_starts = [
    [0.000, 2.848],
    [0.000, 3.945, 5.451],
    [0.000, 1.971, 3.764],
    [0.000, 1.498],
    [0.000, 1.863, 3.574],
    [0.000, 1.742, 3.832],
    [0.000, 3.258, 5.495],
    [0.000, 3.624],
    [0.000, 1.904, 3.747, 5.493],
    [0.000, 2.979],
]

def fmt(seconds):
    ms = round(seconds * 1000)
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

blocks = re.split(r"\n\s*\n", src.read_text(encoding="utf-8").strip())
captions = []
for block in blocks:
    lines = block.splitlines()
    if len(lines) < 3 or "-->" not in lines[1]:
        continue
    text = " ".join(lines[2:]).strip()
    captions.append(text)

out = []
cursor = 0
for scene_idx, starts in enumerate(relative_starts):
    for j, rel_start in enumerate(starts):
        if cursor >= len(captions):
            raise RuntimeError("Caption count does not match sentence onset map")
        start = scene_starts[scene_idx] + rel_start
        next_start = scene_starts[scene_idx] + starts[j + 1] if j + 1 < len(starts) else scene_ends[scene_idx]
        end = max(start + 0.8, next_start - 0.06)
        out.append(f"{cursor + 1}\n{fmt(start)} --> {fmt(end)}\n{captions[cursor]}")
        cursor += 1

if cursor != len(captions):
    raise RuntimeError(f"Unused captions: {len(captions) - cursor}")
dst.write_text("\n\n".join(out) + "\n", encoding="utf-8")
print(dst)
