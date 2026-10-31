from pathlib import Path
import json, re, subprocess
import soundfile as sf
import numpy as np

ROOT = Path(__file__).resolve().parent
AUDIO = ROOT / "audio"
RATE = 24000
TEMPO = 0.75
sentence_gap = 0.30
scene_gap = {2:0.90, 5:0.90, 8:0.90, 10:1.00, 13:1.00, 16:1.00, 19:1.00, 21:2.00, 25:1.10}

cfg = json.loads((ROOT / "story_config.json").read_text(encoding="utf-8-sig"))
sentences = []
for scene in cfg["scenes"]:
    parts = [x.strip() for x in re.split(r"(?<=[.!?])\s+", scene["caption"]) if x.strip()]
    sentences.extend(parts)

audio_parts = []
for idx, text in enumerate(sentences, 1):
    src = AUDIO / f"v2_sentence_{idx:02d}.wav"
    slowed = AUDIO / f"v2_sentence_slow_{idx:02d}.wav"
    subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error","-i",str(src),"-af",f"atempo={TEMPO}","-ar",str(RATE),"-ac","1",str(slowed)],check=True)
    data, rate = sf.read(str(slowed), dtype="float32")
    active = np.where(np.abs(data) > 0.008)[0]
    first = max(0, int(active[0]) - round(rate * 0.03))
    last = min(len(data), int(active[-1]) + round(rate * 0.04))
    audio_parts.append(data[first:last])

timeline_sentences = []
timeline_scenes = []
parts = []
cursor = 0.0
sentence_idx = 0
for scene_idx, scene in enumerate(cfg["scenes"], 1):
    scene_start = cursor
    scene_sentence_ids = []
    last_speech_end = cursor
    count = len([x for x in re.split(r"(?<=[.!?])\s+", scene["caption"]) if x.strip()])
    for _ in range(count):
        sentence_idx += 1
        data = audio_parts[sentence_idx - 1]
        start = cursor
        duration = len(data) / RATE
        parts.append(data)
        cursor += duration
        end = cursor
        last_speech_end = end
        scene_sentence_ids.append(sentence_idx)
        timeline_sentences.append({"id": sentence_idx, "scene": scene["id"], "text": sentences[sentence_idx - 1], "start": round(start, 3), "end": round(end, 3), "caption_start": round(start, 3), "caption_end": round(end, 3)})
        if sentence_idx < len(sentences):
            pause = scene_gap.get(sentence_idx, sentence_gap)
            parts.append(np.zeros(round(pause * RATE), dtype="float32"))
            cursor += pause
    scene_end = cursor
    timeline_scenes.append({"id": scene["id"], "asset": scene["asset"], "start": round(scene_start, 3), "speech_end": round(last_speech_end, 3), "end": round(scene_end, 3), "sentence_ids": scene_sentence_ids})

final_pause = 2.0
parts.append(np.zeros(round(final_pause * RATE), dtype="float32"))
cursor += final_pause
sf.write(str(AUDIO / "narration_v2.wav"), np.concatenate(parts), RATE, subtype="FLOAT")

timeline = {
    "version": 2,
    "master_clock": "audio/narration_v2.wav",
    "sample_rate": RATE,
    "runtime_seconds": round(cursor, 3),
    "narration": {"tempo_factor": TEMPO, "sentence_pause_seconds": sentence_gap, "final_resonance_seconds": final_pause, "sentences": timeline_sentences},
    "scenes": timeline_scenes,
    "music": {"intro": [0.0, timeline_scenes[1]["start"]], "drums": [timeline_scenes[1]["start"], timeline_scenes[3]["end"]], "battle": [timeline_scenes[3]["start"], timeline_scenes[7]["end"]], "rebirth": [timeline_scenes[8]["start"], round(cursor-final_pause,3)]},
    "sfx": {"duck_to_narration": True, "surtr_silence_start": timeline_scenes[7]["end"] - 2.0, "surtr_silence_end": timeline_scenes[8]["start"]}
}
(ROOT / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"runtime": timeline["runtime_seconds"], "scenes": timeline_scenes}, ensure_ascii=False))
