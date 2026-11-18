# Living Tapestries review protocol

Every delivery requires two independent reviews after rendering.

## Procedural pipeline audit

Trace the actual artifact chain:

`authoritative JSON -> effective narration text -> TTS cache -> narration.wav -> word alignment -> SRT -> panorama timeline -> rendered MP4 -> final mixed audio`

The reviewer must confirm:

- The effective TTS text is derived from the current JSON and each cache has one canonical `spoken_text` field.
- The final mixed audio was built from the current narration waveform, verified by `audio/audio_manifest.json` hashes.
- Timeline asset paths exist and identify the same H panorama files the renderer uses.
- Narration, mix, MP4, timeline, and SRT runtimes agree within policy tolerances.
- Captions do not overlap, lead speech, linger into authored silence, or disagree with the timeline.
- Stale QA reports, old runtime reports, and old audio stems are not being presented as current evidence.

## Adversarial render review

## Natural-speech review

Inspect the effective TTS text, cache, word timing artifacts, and rendered audio for:

- merged adjacent words;
- missing clause separation;
- awkward provenance flow;
- duplicate or malformed words;
- encoding artifacts;
- unnatural internal pauses.

Audition the rendered audio when playback is available and record the limitation when it is not.

Inspect the encoded MP4 and sampled frames, not only JSON fields. Check:

- The first hook is present once and the provenance/source phrase is not duplicated.
- The actual TTS and captions do not repeat words that are absent from the story.
- Each scene reveals three distinct visual developments with smooth, purposeful horizontal travel.
- Scene transitions have no black flash, crop teleport, frozen frame, or accidental intermediate scene.
- Artwork is culture-specific, artful, and readable on a phone rather than generic or cartoonish.
- Audio is present, narration remains intelligible, and no stale mix or caption version is being delivered.

Both reviews must report unresolved limitations, including unavailable live playback or missing optional stems. A passing FFmpeg exit code is never sufficient for delivery.
