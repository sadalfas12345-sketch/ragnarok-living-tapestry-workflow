# Reusable illustrated-story workflow

This project is a reusable vertical story pipeline. Replace the scene assets and `story_config.json`, then run:

```powershell
python assemble_segments.py
powershell -ExecutionPolicy Bypass -File build_mixkit_soundtrack.ps1
powershell -ExecutionPolicy Bypass -File qa_gates.ps1
```

The story manifest is intentionally generic. Each scene declares its time range, artwork, caption text, and required visual beats. The QA gates check timing, format, asset uniqueness, caption text alignment, and camera-motion safety. Human visual review is still required for whether each required visual beat is actually depicted.

The soundtrack builder keeps narration, music, and SFX as separate stems, applies narration-driven ducking, and checks loudness and peaks with FFmpeg. Music sources and license evidence belong in `music_sources.json`.
