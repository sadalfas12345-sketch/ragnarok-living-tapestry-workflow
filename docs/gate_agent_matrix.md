# Gate and multi-agent matrix

Episode 32 actual status: all listed gates PASS.

| Gate | Multi-agent | Owner | Evidence | Status |
|---|---|---|---|---|
| lifecycle_monitoring | No | Lifecycle + watchdog | Heartbeat, child process, terminal state | PASS |
| failure_prevention_gates | No | Delivery gate | Hash, render identity, Drive evidence | PASS |
| continuation_policy | No | Lifecycle policy | Continue until all hard gates pass | PASS |
| camera | No | Renderer + visual gates | Smooth rightward path, no shake or crop reset | PASS |
| scenes | Yes | audience_emotion_gate + adversarial_render_review | Three beats, concrete story, emotional turn | PASS |
| artwork | Yes | historical_scene + anatomy + adversarial + line agents | Culture, period, anatomy, seams, style | PASS |
| scene_contrast | Yes | adversarial_render_review | Adjacent scenes visibly distinct | PASS |
| line_artifact_review | Yes | line_artifact_agent | Rendered intra-scene seam scan | PASS |
| provenance | Yes | wording_agent + procedural_pipeline_audit | What-if source phrase and deduplication | PASS |
| rendered_caption_text | Yes | wording_agent + natural_speech_review | No mojibake or malformed text | PASS |
| prose | Yes | wording_agent + natural_speech_review | Plain, natural, non-bureaucratic narration | PASS |
| name_spelling_review | Yes | name_spelling_agent | Canonical names and spelling | PASS |
| historical_scene_review | Yes | historical_scene_agent | Period and historical coherence | PASS |
| wording_review | Yes | wording_agent | Repetition and awkward joins | PASS |
| word_timing | No | Timing QA + waveform | Measured word gaps and scene pauses | PASS |
| natural_speech_review | Yes | natural_speech_review | Merged words, clause flow, playback when available | PASS |
| captions | No | Timeline/caption QA | Speech boundaries, overlap, silence behavior | PASS |
| audio | No | FFmpeg audio QA | LUFS, true peak, stems, clipping | PASS |
| delivery_integrity | Yes | procedural_pipeline_audit | Timeline, SRT, assets, holistic delivery | PASS |
| multi_agent_review | Yes | Eight required review roles | All enabled reports must PASS | PASS |
| anatomy_review | Yes | anatomy_artifact_agent | Hands, faces, limbs, joints, bodies | PASS |
| pronunciation | Yes | name_spelling_agent + narration | Native lexicon or English fallback | PASS |
| proper_name_pronunciation_gate | Yes | name_spelling_agent | Written spelling matches caption | PASS |
| character_intros | Yes | wording_agent + procedural_pipeline_audit | Short, spoiler-free first-use intro | PASS |
