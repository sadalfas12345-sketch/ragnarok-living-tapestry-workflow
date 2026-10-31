from pathlib import Path
import json, subprocess

ROOT = Path(__file__).resolve().parent
A = ROOT / "audio"
tl = json.loads((ROOT / "timeline.json").read_text(encoding="utf-8"))
runtime = tl["runtime_seconds"]
s2 = tl["scenes"][1]["start"]
s4 = tl["scenes"][3]["start"]
s9 = tl["scenes"][8]["start"]
a = A / "mixkit" / "mixkit_epical_drums_05_grigoriy_nuzhny.mp3"
b = A / "mixkit" / "mixkit_epic_games_ahjay_stelino.mp3"
c = A / "mixkit" / "mixkit_a_new_life_eugenio_mininni.mp3"
bed = A / "music_timeline_v2.wav"
filters = (f"[0:a]atrim=0:15,asetpts=PTS-STARTPTS,lowpass=f=1200,volume=0.32,afade=t=in:st=0:d=3,afade=t=out:st=12:d=3,adelay=0|0[intro];" f"[1:a]atrim=20:{max(20,s4-s2+20):.3f},asetpts=PTS-STARTPTS,volume=0.42,afade=t=in:st=0:d=2,afade=t=out:st={max(2,s4-s2-3):.3f}:d=3,adelay={round(s2*1000)}|{round(s2*1000)}[drums];" f"[2:a]atrim=0:{max(1,s9-s4):.3f},asetpts=PTS-STARTPTS,volume=0.46,afade=t=in:st=0:d=3,afade=t=out:st={max(1,s9-s4-4):.3f}:d=4,adelay={round(s4*1000)}|{round(s4*1000)}[battle];" f"[3:a]atrim=0:{max(1,runtime-s9):.3f},asetpts=PTS-STARTPTS,volume=0.36,afade=t=in:st=0:d=4,afade=t=out:st={max(1,runtime-s9-4):.3f}:d=4,adelay={round(s9*1000)}|{round(s9*1000)}[rebirth];" f"[intro][drums][battle][rebirth]amix=inputs=4:duration=longest:dropout_transition=0,atrim=0:{runtime:.3f},asetpts=PTS-STARTPTS,equalizer=f=3000:t=q:w=1:g=-2,alimiter=limit=0.95[bed]")
subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error","-i",str(a),"-i",str(a),"-i",str(b),"-i",str(c),"-filter_complex",filters,"-map","[bed]","-ar","48000","-ac","2","-c:a","pcm_s24le",str(bed)],check=True)
narr = A / "narration_v2.wav"
sfx = A / "sfx.wav"
final_audio = A / "final_mixed_audio_v2.wav"
mix = f"[0:a]aresample=48000,pan=stereo|c0=c0|c1=c0[n];[1:a]aresample=48000,volume=0.75[s];[2:a]aresample=48000[m];[m][n]sidechaincompress=threshold=0.02:ratio=4:attack=80:release=800:makeup=1:link=average[duck];[n][duck][s]amix=inputs=3:duration=longest:dropout_transition=0,atrim=0:{runtime:.3f},alimiter=limit=0.95,loudnorm=I=-14:TP=-1:LRA=11:print_format=summary[out]"
subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error","-i",str(narr),"-i",str(bed),"-i",str(sfx),"-filter_complex",mix,"-map","[out]","-ar","48000","-ac","2","-c:a","pcm_s24le",str(final_audio)],check=True)
for src, name in [(narr,"narration_stem_v2.wav"),(bed,"music_stem_v2.wav"),(sfx,"sfx_stem_v2.wav")]:
    subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error","-i",str(src),"-t",f"{runtime:.3f}","-c","copy",str(A/name)],check=True)
out = ROOT / "ragnarok_final_v2.mp4"
subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error","-i",str(ROOT/"video_captioned_v2.mp4"),"-i",str(final_audio),"-map","0:v:0","-map","1:a:0","-c:v","copy","-c:a","aac","-b:a","192k","-shortest","-movflags","+faststart",str(out)],check=True)
print(f"output={out} runtime={runtime}")
