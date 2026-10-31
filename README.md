# Illustrated Story Production Workflow

Reusable pipeline for vertical illustrated stories with narration, licensed music, cinematic SFX, eased Ken Burns motion, captions, and automated QA gates.

## Authoritative workflow

1. Put scene artwork in `assets/P01.png`, `P02.png`, and so on.
2. Describe timing, captions, and required visual beats in `story_config.json`.
3. Keep narration, music, and SFX as separate audio stems.
4. Set official music sources and license evidence in `music_sources.json`.
5. Generate sentence-level narration and measure it.
6. Run `compose_timeline_v2.py` to create `timeline.json`.
7. Run `build_srt_from_timeline.py`.
8. Run `render_from_timeline.py`.
9. Run `mix_from_timeline.py`.
10. Run `qa_gates.ps1` before delivery.

`timeline.json` is the only timing authority. It owns narration phrase boundaries, scene boundaries, authored pauses, captions, camera intervals, music cues, SFX cues, and runtime.

For a temporary review export:

```powershell
powershell -ExecutionPolicy Bypass -File make_review_copy.ps1 -InputFile ragnarok_final_v2.mp4 -Speed 1.15
```

Review copies are never production masters.

The gates check timeline/runtime agreement, caption overlap and timeline agreement, sampled caption audit frames, vertical format, scene asset uniqueness, required asset references, and eased camera motion without sinusoidal shake. Human playback review remains required when available.

## Audio rules

- Narration timing is the master clock.
- Music is ducked from the narration signal.
- Music and SFX stay in separate stems.
- Loudness target is approximately -14 LUFS integrated and -1 dBTP maximum true peak.
- Licensed music must be documented before use.

## Story-specific material

The Ragnarök production files and media remain local and are excluded from the public workflow repository. The project manifest and gate design are included as a reusable example.
