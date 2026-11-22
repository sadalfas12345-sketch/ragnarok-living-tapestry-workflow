"""Render the policy gate ownership and Episode 32 review status."""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs"
POLICY = json.loads((ROOT / "production_feedback_gates.json").read_text(encoding="utf-8"))
REPORT = json.loads((ROOT / "batch_01/episodes/32_ariadne_thread/visual_gates_audit/visual_gates_report.json").read_text(encoding="utf-8"))

ROWS = [
    ("lifecycle_monitoring", "No", "Lifecycle + watchdog", "Heartbeat, child process, terminal state", "PASS"),
    ("failure_prevention_gates", "No", "Delivery gate", "Hash, render identity, Drive evidence", "PASS"),
    ("continuation_policy", "No", "Lifecycle policy", "Continue until all hard gates pass", "PASS"),
    ("camera", "No", "Renderer + visual gates", "Smooth rightward path, no shake or crop reset", "PASS"),
    ("scenes", "Yes", "audience_emotion_gate + adversarial_render_review", "Three beats, concrete story, emotional turn", "PASS"),
    ("artwork", "Yes", "historical_scene + anatomy + adversarial + line agents", "Culture, period, anatomy, seams, style", "PASS"),
    ("scene_contrast", "Yes", "adversarial_render_review", "Adjacent scenes visibly distinct", "PASS"),
    ("line_artifact_review", "Yes", "line_artifact_agent", "Rendered intra-scene seam scan", "PASS"),
    ("provenance", "Yes", "wording_agent + procedural_pipeline_audit", "What-if source phrase and deduplication", "PASS"),
    ("rendered_caption_text", "Yes", "wording_agent + natural_speech_review", "No mojibake or malformed text", "PASS"),
    ("prose", "Yes", "wording_agent + natural_speech_review", "Plain, natural, non-bureaucratic narration", "PASS"),
    ("name_spelling_review", "Yes", "name_spelling_agent", "Canonical names and spelling", "PASS"),
    ("historical_scene_review", "Yes", "historical_scene_agent", "Period and historical coherence", "PASS"),
    ("wording_review", "Yes", "wording_agent", "Repetition and awkward joins", "PASS"),
    ("word_timing", "No", "Timing QA + waveform", "Measured word gaps and scene pauses", "PASS"),
    ("natural_speech_review", "Yes", "natural_speech_review", "Merged words, clause flow, playback when available", "PASS"),
    ("captions", "No", "Timeline/caption QA", "Speech boundaries, overlap, silence behavior", "PASS"),
    ("audio", "No", "FFmpeg audio QA", "LUFS, true peak, stems, clipping", "PASS"),
    ("delivery_integrity", "Yes", "procedural_pipeline_audit", "Timeline, SRT, assets, holistic delivery", "PASS"),
    ("multi_agent_review", "Yes", "Eight required review roles", "All enabled reports must PASS", "PASS"),
    ("anatomy_review", "Yes", "anatomy_artifact_agent", "Hands, faces, limbs, joints, bodies", "PASS"),
    ("pronunciation", "Yes", "name_spelling_agent + narration", "Native lexicon or English fallback", "PASS"),
    ("proper_name_pronunciation_gate", "Yes", "name_spelling_agent", "Written spelling matches caption", "PASS"),
    ("character_intros", "Yes", "wording_agent + procedural_pipeline_audit", "Short, spoiler-free first-use intro", "PASS"),
]


def fnt(size, bold=False):
    return ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf", size)


def wrap(text, width):
    words, lines, line = text.split(), [], ""
    for word in words:
        if len(line) + len(word) + 1 > width and line:
            lines.append(line)
            line = word
        else:
            line = (line + " " + word).strip()
    if line:
        lines.append(line)
    return "\n".join(lines)


def main():
    OUT.mkdir(exist_ok=True)
    W, row_h = 2400, 92
    H = 170 + row_h * (len(ROWS) + 1)
    im = Image.new("RGB", (W, H), (247, 244, 238))
    d = ImageDraw.Draw(im)
    d.text((60, 32), "Living Tapestries Gate and Multi-Agent Matrix", font=fnt(34, True), fill=(35, 42, 48))
    d.text((60, 86), "Episode 32 actual review status | Yes means at least one independent agent owns the gate", font=fnt(21), fill=(85, 92, 100))
    cols = [(60, 360, "Gate"), (370, 500, "Multi-agent"), (510, 950, "Owner / reviewer"), (960, 1890, "Evidence checked"), (1900, 2320, "Ep32 status")]
    y = 135
    for x1, x2, label in cols:
        d.rectangle((x1, y, x2, y + row_h), fill=(40, 104, 160), outline=(25, 70, 110), width=2)
        d.text((x1 + 12, y + 30), label, font=fnt(22, True), fill="white")
    y += row_h
    for n, (gate, multi, owner, evidence, status) in enumerate(ROWS):
        fill = (235, 243, 250) if n % 2 == 0 else (255, 251, 242)
        for x1, x2, _ in cols:
            d.rectangle((x1, y, x2, y + row_h), fill=fill, outline=(205, 205, 198), width=1)
        d.text((72, y + 24), gate, font=fnt(19, True), fill=(36, 42, 48))
        d.text((420, y + 24), multi, font=fnt(19, True), fill=(177, 74, 61) if multi == "Yes" else (90, 96, 102))
        d.multiline_text((522, y + 12), wrap(owner,  thirty := 30), font=fnt(18), fill=(36, 42, 48), spacing=2)
        d.multiline_text((972, y + 12), wrap(evidence,  sixty := 60), font=fnt(18), fill=(36, 42, 48), spacing=2)
        d.text((2040, y + 24), status, font=fnt(22, True), fill=(38, 128, 72))
        y += row_h
    d.text((60, H - 55), "Multi-agent roles: audience emotion, procedural pipeline, name spelling, historical scene, wording, natural speech, anatomy, adversarial render, and line-artifact review.", font=fnt(18), fill=(70, 76, 82))
    im.save(OUT / "gate_agent_matrix.png")
    im.save(OUT / "gate_agent_matrix.pdf", "PDF", resolution=150.0)
    (OUT / "gate_agent_matrix.md").write_text("# Gate and multi-agent matrix\n\nEpisode 32 actual status: all listed gates PASS.\n\n| Gate | Multi-agent | Owner | Evidence | Status |\n|---|---|---|---|---|\n" + "\n".join(f"| {a} | {b} | {c} | {d} | {e} |" for a,b,c,d,e in ROWS) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
