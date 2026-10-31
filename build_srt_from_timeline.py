from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
tl = json.loads((ROOT / "timeline.json").read_text(encoding="utf-8"))
out = []
def fmt(sec):
    total = round(sec * 1000)
    h, rem = divmod(total, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
for item in tl["narration"]["sentences"]:
    out.append(f"{item['id']}\n{fmt(item['caption_start'])} --> {fmt(item['caption_end'])}\n{item['text']}")
(ROOT / "Captions_final_v2.srt").write_text("\n\n".join(out) + "\n", encoding="utf-8")
print(f"captions={len(out)}")
