# Illustrated Story Production Workflow

Reusable pipeline for vertical illustrated stories with narration, licensed music, cinematic SFX, eased Ken Burns motion, captions, and automated QA gates.

## Workflow

1. Put scene artwork in `assets/P01.png`, `P02.png`, and so on.
2. Describe timing, captions, and required visual beats in `story_config.json`.
3. Keep narration, music, and SFX as separate audio stems.
4. Set official music sources and license evidence in `music_sources.json`.
5. Run `assemble_segments.py`.
6. Run `build_mixkit_soundtrack.ps1`.
7. Run `qa_gates.ps1` before delivery.

The gates check duration, vertical format, scene asset uniqueness, caption text alignment, required asset references, and eased camera motion without sinusoidal shake. Human visual review remains required for confirming that each required visual beat is actually visible in the artwork.

## Audio rules

- Narration timing is the master clock.
- Music is ducked from the narration signal.
- Music and SFX stay in separate stems.
- Loudness target is approximately -14 LUFS integrated and -1 dBTP maximum true peak.
- Licensed music must be documented before use.

## Story-specific material

The Ragnarök production files and media remain local and are excluded from the public workflow repository. The project manifest and gate design are included as a reusable example.
