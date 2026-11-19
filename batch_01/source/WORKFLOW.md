# Living Tapestries: 30-episode batch 01

Each episode JSON is a fully distinct story outline with six original narrated scenes, scene-specific visual prompts, a coherent style-board generation prompt, camera movement, a culturally differentiated sound palette, licensing guidance, and source-integrity notes.

## Pipeline
1. Review every episode’s source-integrity classification. Historical mysteries must not be presented as solved.
2. Generate `references/style_board.png` from `image_reference.style_board_prompt` (NOT included: the JSON specifies it).

Regional style reuse: Indian mythology and folklore may reuse the Nala and Damayanti direction: Rajput miniature illuminated folio, forest greens, pink sandstone palaces, and golden patterns. This is an approved reuse option, not a mandatory style. Historically grounded Indian stories must instead use a culture- and period-relevant visual direction based on their authoritative JSON and historical review.
3. Generate 6 coherent vertical panels `assets/P01.png` to `assets/P06.png` using the story’s scene `image_prompt`.
4. Generate sentence narration **from `scenes[].caption` only**; do not read divergent `audio/Sxx.txt`.
5. Adapt `compose_timeline_v2.py` from Ragnarök so the time authority is final narration WAV; respect `pause_after_seconds_hint`, then derive visual scene and caption timings. DO NOT reuse the stale `start/end/duration_seconds` from the legacy Ragnarök config.
6. Use word-level alignment for short readable captions.
7. Render deterministic Ken Burns/camera motion; compose music and SFX with ducking driven by actual narration; check commercial licenses.
8. QA the actual rendered video: script coverage, scene/caption synchronization, silent beats, image quality, sound masking, full playback.

## Caveats
- `image_reference.status=GENERATE_BEFORE_RENDER` means the story JSON supplies an art-direction prompt, **not an existing photograph or generated style-board file**. Never mark this input complete until the style board exists.
- The story text is original paraphrase, not verbatim copyrighted translation.
- This package is editorial/production-ready JSON, not proof that the visual assets were produced or that all fact checks passed.
- The current Ragnarök repo does not natively support all added scene fields and requires the adapter described above.
