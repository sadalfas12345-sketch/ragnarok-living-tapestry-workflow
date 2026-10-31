# Reusable illustrated-story workflow

This project is a reusable vertical story pipeline. Replace the scene assets and story text, regenerate sentence-level narration, then run:

```powershell
python compose_timeline_v2.py
python build_srt_from_timeline.py
python render_from_timeline.py
python mix_from_timeline.py
powershell -ExecutionPolicy Bypass -File qa_gates.ps1
```

`timeline.json` is the only timing authority. It is derived from measured narration audio and contains phrase timings, scene boundaries, intentional pauses, caption timings, music cues, SFX cues, and total runtime. Do not maintain parallel scene-duration or caption timestamp arrays.

The QA gates fail on timeline/runtime mismatch, overlapping captions, captions that disagree with the timeline, missing narration, or a failed sampled caption audit. Human playback review is still required when available.

The soundtrack builder keeps narration, music, and SFX as separate stems, applies narration-driven ducking, and checks loudness and peaks with FFmpeg. Music sources and license evidence belong in `music_sources.json`.
