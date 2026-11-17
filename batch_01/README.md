# Living Tapestries Batch 01

Batch 01 contains 30 six-scene episodes. The source JSON is authoritative for
story text, cultural art direction, camera intent, music cues, SFX cues,
pause hints, and source-integrity classification.

The production adapter is deliberately separate from the Ragnarök assets. It
uses the final narration waveform as the master clock, aligns captions from
measured Whisper word timestamps, and records independent QA results.

## Workflow

1. Validate all 30 source JSONs:

```powershell
$env:FFMPEG = 'C:\Program Files\Virtual Desktop Streamer\ffmpeg.exe'
$env:FFPROBE = 'C:\Program Files\Virtual Desktop Streamer\ffprobe.exe'
$env:Path = 'C:\Program Files\Virtual Desktop Streamer;' + $env:Path
python batch_01\batch_runner.py --stage validate
```

2. Generate the selected episode's style board and six panels from its
`image_reference.style_board_prompt` and `scenes[].image_prompt`. The runner
will fail closed until all seven files exist.

3. Run one episode, with resumable stage statuses:

```powershell
python batch_01\run_batch.py --episode 1 --stage all --resume
```

4. Run the full batch only after the representative episode passes:

```powershell
python batch_01\run_batch.py --all --stage all --resume
```

Each episode gets `batch_01/status/NN.json`. Missing or changed source JSONs
invalidate the cached stage status. Generated media stays outside Git history;
the status files and QA reports are the production record.

## Editorial safety

Every source file is labeled as myth, oral tradition, literary retelling,
historical account, or unresolved mystery. `research_status` is carried into
the QA report. Episodes marked as needing source review must not be presented
as settled history until that review is completed.

Stock music is documented per episode with source and license URLs. The
default representative arrangement uses the verified Mixkit cache already in
this workspace. Synthetic SFX are generated locally and have no third-party
attribution requirement.

## Visual direction gates

Each episode must use its own authoritative `civilization`,
`image_reference.art_style`, `image_reference.palette`, and scene
`image_prompt` direction. Artwork should express the culture's materials,
clothing, architecture, landscape, ornament, and visual tradition while
remaining cinematic and legible on a phone. A generic historical-painting
treatment must not be reused across unrelated cultures.

The finish must read as artful, museum-quality work rather than cartoon,
comic-book, glossy game-poster, or generic stock illustration. Cultural
specificity and high-end fine-art composition are required without forcing
photorealism.

Every scene remains a left-to-right three-beat panorama, but adjacent scenes
must also be meaningfully different. Rendered QA compares opening, middle, and
ending samples between neighboring scenes and fails when they are too similar.
When that gate fails, regenerate the deficient scene with a different
narrative composition; do not hide the problem with a faster camera move or a
crop reset.

Provenance bridges are deduplicated before narration. If the authoritative
caption already says “in Arabian Nights tradition,” the pipeline must not add
another “tradition.” Repeated provenance terms fail QA before delivery.
