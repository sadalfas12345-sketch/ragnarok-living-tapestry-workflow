from pathlib import Path
import soundfile as sf
import numpy as np

ROOT = Path(__file__).resolve().parent
audio = ROOT / "audio"
out = audio / "narration_woman_compact.wav"
gap_frames = 2880  # 120 ms at 24 kHz

parts = []
sample_rate = None
for i in range(1, 11):
    path = audio / f"chatterbox_S{i:02d}.wav"
    samples, rate = sf.read(str(path), dtype="float32")
    if samples.ndim != 1:
        raise RuntimeError(f"Expected mono WAV: {path}")
    sample_rate = rate if sample_rate is None else sample_rate
    window = max(1, int(rate * 0.01))
    active = []
    for start in range(0, len(samples), window):
        chunk = samples[start:start + window]
        rms = float(np.sqrt(np.mean(chunk * chunk)))
        if rms > 0.008:
            active.append((start, min(len(samples), start + window)))
    if not active:
        raise RuntimeError(f"No speech detected: {path}")
    first = max(0, active[0][0] - int(rate * 0.02))
    last = min(len(samples), active[-1][1] + int(rate * 0.03))
    parts.append(samples[first:last])

gap = np.zeros(gap_frames, dtype="float32")
combined = np.concatenate([x for idx, part in enumerate(parts) for x in ((part, gap) if idx < len(parts) - 1 else (part,))])
sf.write(str(out), combined, sample_rate, subtype="FLOAT")

cursor = 0.0
starts = []
for idx, part in enumerate(parts):
    starts.append(cursor)
    cursor += len(part) / sample_rate
    if idx < len(parts) - 1:
        cursor += gap_frames / sample_rate
print(f"output={out} duration={cursor:.3f}")
print("scene_starts=" + ",".join(f"{x:.3f}" for x in starts))
