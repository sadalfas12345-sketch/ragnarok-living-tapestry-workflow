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
10. Run `qa_gates.ps1 -Episode 7` before delivery.

`timeline.json` is the only timing authority. It owns narration phrase boundaries, scene boundaries, authored pauses, captions, camera intervals, music cues, SFX cues, and runtime.

`production_feedback_gates.json` is the reusable production policy derived from review feedback. It requires narration-led timing, smooth rightward story travel, three distinct visual beats, no shake or hard crop resets, natural transitions, caption discipline, and rendered-output verification. Episode-specific code must not override these gates.

For a temporary review export:

```powershell
powershell -ExecutionPolicy Bypass -File make_review_copy.ps1 -InputFile ragnarok_final_v2.mp4 -Speed 1.15
```

Review copies are never production masters.

The V2 gates inspect the encoded MP4, not only its inputs. They check timeline/runtime agreement, caption overlap and bounds, three-point visual progression in every scene, horizontal direction declarations, output dimensions and delivery bitrate, black or frozen transition frames, and transition continuity. The legacy root-level files are not used as timing authority. Human playback review remains required when available.

Run the gates directly with:

```powershell
python batch_01/visual_gates_v2.py --episode 7
```

`examples/episode_07_hou_yi_input.example.json` is a complete episode input example showing the three-beat visual progression schema.

## Audio rules

- Narration timing is the master clock.
- Music is ducked from the narration signal.
- Music and SFX stay in separate stems.
- Loudness target is approximately -14 LUFS integrated and -1 dBTP maximum true peak.
- Licensed music must be documented before use.

## Story-specific material

The Ragnarök production files and media remain local and are excluded from the public workflow repository. The project manifest and gate design are included as a reusable example.
