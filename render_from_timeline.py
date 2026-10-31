from pathlib import Path
import json, subprocess

ROOT = Path(__file__).resolve().parent
tl = json.loads((ROOT / "timeline.json").read_text(encoding="utf-8"))
work = ROOT / "video_segments_v2"
work.mkdir(exist_ok=True)
fps = 30
scene_files = []
for idx, scene in enumerate(tl["scenes"], 1):
    dur = scene["end"] - scene["start"]
    frames = round(dur * fps)
    out = work / f"S{idx:02d}.mp4"
    p = f"(1-cos(on/{max(frames-1,1)}*PI))/2"
    z = f"1+0.10*{p}"
    x = f"iw/2-(iw/zoom/2)+{(idx%3-1)*80}*{p}"
    y = f"ih/2-(ih/zoom/2)+{((idx+1)%3-1)*110}*{p}"
    vf = f"zoompan=z={z}:x={x}:y={y}:d={frames}:s=1080x1920:fps=30,format=yuv420p,fade=t=in:st=0:d=0.18,fade=t=out:st={max(0,dur-0.18):.3f}:d=0.18"
    subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error","-loop","1","-i",str(ROOT / scene["asset"]),"-vf",vf,"-frames:v",str(frames),"-an","-c:v","libx264","-preset","veryfast","-b:v","350k","-maxrate","450k","-bufsize","700k",str(out)],check=True)
    scene_files.append(out)
concat = work / "concat.txt"
concat.write_text("\n".join(f"file '{p.resolve()}'" for p in scene_files), encoding="utf-8")
video_only = work / "video_only.mp4"
subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error","-f","concat","-safe","0","-i",str(concat),"-vf","tpad=stop_mode=clone:stop_duration=2","-an","-c:v","libx264","-preset","veryfast","-b:v","350k","-maxrate","450k","-bufsize","700k",str(video_only)],check=True)
sub = (ROOT / "Captions_final_v2.srt").resolve().as_posix().replace(":", "\\:")
subf = f"subtitles=filename='{sub}':force_style='FontName=Georgia,FontSize=18,PrimaryColour=&H00F5F1E8,OutlineColour=&H80000000,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=125'"
subbed = ROOT / "video_captioned_v2.mp4"
subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error","-i",str(video_only),"-vf",subf,"-an","-c:v","libx264","-preset","veryfast","-b:v","350k","-maxrate","450k","-bufsize","700k",str(subbed)],check=True)
print(f"video={subbed} runtime={tl['runtime_seconds']}")
