# Audio QA — Episode 17

- Final mixed audio: `audio/final_mixed_audio.wav`
- Format: 48 kHz stereo WAV master
- Measured integrated loudness: -14.2 LUFS
- Measured true peak: -1.0 dBTP
- Measured loudness range: 3.7 LU
- Loudness-normalized estimate: -14.1 LUFS, -1.0 dBTP
- Narration ducking: narration-led mix with smooth 60 ms attack and 700 ms release
- Separate stems: narration, music, and SFX present
- Soundtrack profile: `savitri_death_bargain`
- Music licensing: Mixkit Free Music policy recorded in `music_sources.json`; no attribution required under the recorded policy
- Auditory playback: unavailable to the agent. Waveform, loudness, rendered-frame, caption, and synchronization checks completed.

## Checks

- No clipping reported by the peak measurement.
- Timeline and rendered video durations agree within encoder rounding.
- Caption overlap count: 0.
- Human listening on phone speakers and headphones remains pending because playback audition is unavailable in this environment.
