$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$mix = Join-Path $root 'audio\mixkit'
$narr = Join-Path $root 'audio\narration_woman_compact.wav'
$sfx = Join-Path $root 'audio\sfx.wav'
$a = Join-Path $mix 'mixkit_epical_drums_05_grigoriy_nuzhny.mp3'
$b = Join-Path $mix 'mixkit_epic_games_ahjay_stelino.mp3'
$c = Join-Path $mix 'mixkit_a_new_life_eugenio_mininni.mp3'
$bed = Join-Path $root 'audio\music_mixkit_ducked.wav'
$ducked = Join-Path $root 'audio\music_mixkit_ducked_tmp.wav'
$final = Join-Path $root 'audio\final_mixed_audio_mixkit.wav'

# Build a restrained 80-second music bed. The intro is low-passed and quiet,
# the battle excerpts are separated by a deliberate near-silence, and the
# rebirth cue enters only at the end.
& ffmpeg -y -hide_banner -loglevel error `
  -i $a -i $a -i $b -i $c `
  -filter_complex "[0:a]atrim=0:15,asetpts=PTS-STARTPTS,lowpass=f=1200,volume=0.35,afade=t=in:st=0:d=3,afade=t=out:st=12:d=3,adelay=0|0[intro];[1:a]atrim=20:36,asetpts=PTS-STARTPTS,volume=0.45,afade=t=in:st=0:d=2,afade=t=out:st=13:d=3,adelay=15000|15000[a];[2:a]atrim=0:34,asetpts=PTS-STARTPTS,volume=0.48,afade=t=in:st=0:d=3,afade=t=out:st=30:d=4,adelay=31000|31000[b];[3:a]atrim=0:10,asetpts=PTS-STARTPTS,volume=0.38,afade=t=in:st=0:d=3,afade=t=out:st=7:d=3,adelay=70000|70000[c];[intro][a][b][c]amix=inputs=4:duration=longest:dropout_transition=0,apad,atrim=0:81.45,asetpts=PTS-STARTPTS,equalizer=f=3000:t=q:w=1:g=-2,alimiter=limit=0.95[bed]" `
  -map "[bed]" -ar 48000 -ac 2 -c:a pcm_s24le $bed

# Narration-driven ducking with smooth attack and release. The original
# narration and synthesized SFX remain unchanged; only music is processed.
& ffmpeg -y -hide_banner -loglevel error `
  -i $bed -i $narr `
  -filter_complex "[0:a]sidechaincompress=threshold=0.02:ratio=4:attack=80:release=800:makeup=1:link=average[ducked]" `
  -map "[ducked]" -ar 48000 -ac 2 -c:a pcm_s24le $ducked
Move-Item $ducked $bed -Force

# Mix narration, ducked music, and the existing SFX bed. Keep headroom before
# loudness normalization, then target a streaming-safe integrated level.
& ffmpeg -y -hide_banner -loglevel error `
  -i $narr -i $bed -i $sfx `
  -filter_complex "[0:a]aresample=48000,pan=stereo|c0=c0|c1=c0[n];[1:a]aresample=48000[m];[2:a]aresample=48000,volume=0.75[s];[n][m][s]amix=inputs=3:duration=longest:dropout_transition=0,alimiter=limit=0.95,loudnorm=I=-14:TP=-1:LRA=11:print_format=summary[out]" `
  -map "[out]" -ar 48000 -ac 2 -c:a pcm_s24le $final

# Make the final music stem and normalized delivery stems available separately.
Copy-Item $narr (Join-Path $root 'audio\narration_stem.wav') -Force
Copy-Item $sfx (Join-Path $root 'audio\sfx_stem.wav') -Force
Copy-Item $bed (Join-Path $root 'audio\music_stem_mixkit_ducked.wav') -Force

# Replace only the audio stream; all video, captions, and visuals remain intact.
$video = Join-Path $root 'final_vertical_1080x1920.mp4'
$outVideo = Join-Path $root 'ragnarok_final.mp4'
& ffmpeg -y -hide_banner -loglevel error -i $video -i $final -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart $outVideo
