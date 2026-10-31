from pathlib import Path
import re

root = Path(__file__).resolve().parent
src = root / "Captions_v15.srt"
dst = root / "Captions_v16.srt"

old_bounds = [0.000, 9.373, 21.449, 33.501, 45.663, 57.327, 69.318, 81.977, 92.804, 107.500, 118.000]
new_bounds = [0.000, 9.373, 19.873, 33.501, 45.663, 57.327, 69.300, 81.961, 92.843, 107.477, 117.977]

def parse_time(value):
    h, m, rest = value.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

def fmt_time(seconds):
    total_ms = round(seconds * 1000)
    h, rem = divmod(total_ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

blocks = re.split(r"\n\s*\n", src.read_text(encoding="utf-8").strip())
out = []
for block in blocks:
    lines = block.splitlines()
    if len(lines) < 3 or "-->" not in lines[1]:
        continue
    start_text, end_text = [x.strip() for x in lines[1].split("-->")]
    start = parse_time(start_text)
    end = parse_time(end_text)
    scene = max(0, min(9, next((i for i in range(10) if old_bounds[i] <= start < old_bounds[i + 1]), 9)))
    old_start, old_end = old_bounds[scene], old_bounds[scene + 1]
    new_start, new_end = new_bounds[scene], new_bounds[scene + 1]
    scale = (new_end - new_start) / (old_end - old_start)
    mapped_start = new_start + (start - old_start) * scale
    mapped_end = new_start + (end - old_start) * scale
    out.append("\n".join([lines[0], f"{fmt_time(mapped_start)} --> {fmt_time(mapped_end)}", *lines[2:]]))

dst.write_text("\n\n".join(out) + "\n", encoding="utf-8")
print(dst)
