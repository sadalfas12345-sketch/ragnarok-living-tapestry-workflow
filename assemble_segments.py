import subprocess, json
from pathlib import Path
R=Path(__file__).resolve().parent; V=R/'assets'; A=R/'audio'; W=R/'video_segments'; W.mkdir(exist_ok=True)
raw=[9.373,10.500,13.628,12.162,11.664,11.973,12.661,10.882,14.634,10.500]; d=raw
for i,du in enumerate(d,1):
 out=W/f'S{i:02d}.mp4'
 frames=round(du*30)
 p=f"(1-cos(on/{max(frames-1,1)}*PI))/2"; z=f"1+0.10*{p}"; x=f"iw/2-(iw/zoom/2)+{(i%3-1)*80}*{p}"; y=f"ih/2-(ih/zoom/2)+{((i+1)%3-1)*110}*{p}"
 vf=f"zoompan=z={z}:x={x}:y={y}:d={frames}:s=1080x1920:fps=30,format=yuv420p"
 subprocess.run(['ffmpeg','-y','-loop','1','-i',str(V/f'P{i:02d}.png'),'-vf',vf,'-frames:v',str(frames),'-an','-c:v','libx264','-preset','veryfast','-b:v','350k','-maxrate','450k','-bufsize','700k',str(out)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
lst=W/'concat.txt'; lst.write_text('\n'.join("file '"+str((W/f'S{i:02d}.mp4').resolve()).replace("'","'\\''")+"'" for i in range(1,11)),encoding='utf-8')
vid=W/'video_only.mp4'; subprocess.run(['ffmpeg','-y','-f','concat','-safe','0','-i',str(lst),'-c','copy',str(vid)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
sub=str((R/'Captions_v15.srt').resolve()).replace('\\','/').replace(':','\\:')
fc="[1:a]atempo=1.0[n];[2:a]volume=0.28[m];[3:a]volume=0.5[s];[n][m][s]amix=inputs=3:duration=longest:normalize=0,loudnorm=I=-14:TP=-1:LRA=11[a]"
subf=f"subtitles=filename='{sub}':force_style='FontName=Georgia,FontSize=18,PrimaryColour=&H00F5F1E8,OutlineColour=&H80000000,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=125'"
subprocess.run(['ffmpeg','-y','-i',str(vid),'-i',str(A/'narration.wav'),'-i',str(A/'music.wav'),'-i',str(A/'sfx.wav'),'-filter_complex',fc,'-map','0:v','-map','[a]','-vf',subf,'-t','118','-r','30','-c:v','libx264','-preset','veryfast','-b:v','350k','-maxrate','450k','-bufsize','700k','-c:a','aac','-b:a','128k','-movflags','+faststart',str(R/'final_vertical_1080x1920.mp4')],check=True)
print({'duration_sec':118,'segments':10})
