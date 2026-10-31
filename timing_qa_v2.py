from pathlib import Path
import json, re, subprocess
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
tl = json.loads((ROOT / "timeline.json").read_text(encoding="utf-8"))
srt = (ROOT / "Captions_final_v2.srt").read_text(encoding="utf-8")
blocks = re.split(r"\n\s*\n", srt.strip())
caps = []
def parse(v):
    h,m,rest=v.split(":"); s,ms=rest.split(","); return int(h)*3600+int(m)*60+int(s)+int(ms)/1000
for b in blocks:
    lines=b.splitlines(); a,z=[x.strip() for x in lines[1].split("-->")]; caps.append((parse(a),parse(z)," ".join(lines[2:])))
fail=[]
for i,(a,z,_) in enumerate(caps):
    if z <= a: fail.append(f"caption {i+1} has non-positive duration")
    if i and a < caps[i-1][1]-0.001: fail.append(f"caption overlap {i} -> {i+1}")
    expected=tl["narration"]["sentences"][i]
    if abs(a-expected["caption_start"])>0.001 or abs(z-expected["caption_end"])>0.001: fail.append(f"caption {i+1} disagrees with timeline")
probe=json.loads(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","json",str(ROOT/"ragnarok_final_v2.mp4")],text=True))
runtime=float(probe["format"]["duration"])
if abs(runtime-tl["runtime_seconds"])>0.08: fail.append(f"video runtime {runtime:.3f} != timeline {tl['runtime_seconds']:.3f}")
audit=ROOT/"caption_audit_v2"; audit.mkdir(exist_ok=True)
thumbs=[]
for i,(a,_,_) in enumerate(caps,1):
    out=audit/f"caption_{i:02d}.jpg"
    subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error","-ss",f"{max(0,a+0.05):.3f}","-i",str(ROOT/"ragnarok_final_v2.mp4"),"-frames:v","1","-vf","scale=180:320",str(out)],check=True)
    thumbs.append(Image.open(out).convert("RGB"))
sheet=Image.new("RGB",(180*6,350*((len(thumbs)+5)//6)),"black")
d=ImageDraw.Draw(sheet)
for i,img in enumerate(thumbs):
    x=(i%6)*180; y=(i//6)*350; sheet.paste(img,(x,y)); d.text((x+4,y+322),f"caption {i+1}",(255,255,255))
sheet.save(ROOT/"caption_audit_v2_contact_sheet.jpg",quality=90)
lines=["# Timing QA v2", "", f"Timeline runtime: {tl['runtime_seconds']:.3f} s", f"Rendered runtime: {runtime:.3f} s", f"Caption count: {len(caps)}", f"Caption overlaps: {sum(1 for i in range(1,len(caps)) if caps[i][0] < caps[i-1][1]-0.001)}", "", "Scene pauses:"]
for i in range(1,len(tl["scenes"])):
    prev=tl["scenes"][i-1]; cur=tl["scenes"][i]; lines.append(f"- {prev['id']} -> {cur['id']}: {cur['start']-prev['speech_end']:.3f} s")
lines += ["", "Caption audit: caption_audit_v2_contact_sheet.jpg", "", "Result: " + ("PASS" if not fail else "FAIL")]
if fail: lines += ["", "Failures:"] + [f"- {x}" for x in fail]
(ROOT/"timing_qa_report.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
print("PASS timing QA" if not fail else "FAIL timing QA\n"+"\n".join(fail))
raise SystemExit(0 if not fail else 1)
