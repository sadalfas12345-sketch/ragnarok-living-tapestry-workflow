from pathlib import Path
import re
import torch
import torchaudio as ta
from chatterbox.tts import ChatterboxTTS

ROOT = Path(__file__).resolve().parent
AUDIO = ROOT / "audio"
PROMPT = AUDIO / "voice_reference_unicorn.wav"
texts = []
for i in range(1, 11):
    scene = (AUDIO / f"S{i:02d}.txt").read_text(encoding="utf-8").strip()
    texts.extend([x.strip() for x in re.split(r"(?<=[.!?])\s+", scene) if x.strip()])

device = "cuda" if torch.cuda.is_available() else "cpu"
model = ChatterboxTTS.from_pretrained(device=device)
for idx, text in enumerate(texts, 1):
    out = AUDIO / f"v2_sentence_{idx:02d}.wav"
    wav = model.generate(text=text, audio_prompt_path=str(PROMPT), exaggeration=0.55, cfg_weight=0.55)
    ta.save(str(out), wav.cpu(), model.sr)
    print(f"{idx:02d} {out.name} {text}", flush=True)
print(f"generated={len(texts)} device={device}")
