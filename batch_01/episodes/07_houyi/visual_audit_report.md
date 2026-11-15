# Episode 07 authoritative v2 horizontal visual beat audit

Rendered file: `ragnarok_episode_07_authoritative_v2_burned.mp4`

The encoded MP4 was sampled at each scene's opening, development, reveal, and final transition frames. The contact sheet is `horizontal_audit/horizontal_contact.png`.

| Scene | Opening | Development | Reveal | Result |
|---|---|---|---|---|
| S01 | One sun and ordinary valley | Second and third suns | Ten suns and scorched land | PASS |
| S02 | Dry riverbed | Ruined fields | Suffering people and animals | PASS |
| S03 | Suffering population | Hou Yi arrives | Bow aimed at the suns | PASS |
| S04 | First arrow fires | Separate falling sun-birds | One surviving sun | PASS |
| S05 | Scorched land | Water returns | Green fields and work resumes | PASS |
| S06 | Resting bow and absent suns | Balanced sky | Restored human world | PASS |

Camera continuity: one `zoompan` segment per scene with eased left-to-right interpolation through three subject-centered x-axis anchors and manifest-driven y corrections; no internal cuts, crop jumps, vertical scrolling, or arbitrary hold limit. All six scenes report `travel_axis: horizontal` in `timeline.json`.

Artwork: six 2823×1672 horizontal panoramas were assembled from three compatible 941×1672 tiles per scene. The 1080×1920 viewport therefore enlarges each tile only slightly and avoids the prior 724-pixel panorama source.

Narration alignment: visual anchors use measured phrase starts from the authoritative v2 narration timeline. Captions remain sourced from the same measured timeline and are burned in at the user's request, with the standalone SRT also retained.

Audio and caption QA: pipeline QA status PASS, 26 captions, zero caption overlaps, runtime 61.828 seconds. Encoded-frame audit sampled 24 frames across six scenes, including scene-boundary fades. Auditory playback was unavailable in this environment, so this is a waveform, encoded-frame, caption, and synchronization QA result rather than a human listening claim.
