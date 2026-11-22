"""Render the production workflow as viewable PNG/PDF artifacts."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from workflow_viz.production_graph import EDGES, STAGES


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs"
W, H = 2400, 900
BG = (247, 244, 238)
INK = (36, 42, 48)
BLUE = (40, 104, 160)
GOLD = (191, 137, 29)
RED = (177, 74, 61)


def font(size: int, bold: bool = False):
    name = "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"
    return ImageFont.truetype(name, size)


def centered(draw, xy, text, fnt, fill=INK):
    box = draw.multiline_textbbox((0, 0), text, font=fnt, align="center", spacing=4)
    x, y = xy
    draw.multiline_text((x - (box[2] - box[0]) / 2, y - (box[3] - box[1]) / 2), text, font=fnt, fill=fill, align="center", spacing=4)


def arrow(draw, start, end, color, dashed=False):
    x1, y1 = start
    x2, y2 = end
    if dashed:
        steps = max(1, int(abs(x2 - x1) / 18))
        for i in range(0, steps, 2):
            a = i / steps
            b = min(1, (i + 1) / steps)
            draw.line((x1 + (x2 - x1) * a, y1 + (y2 - y1) * a, x1 + (x2 - x1) * b, y1 + (y2 - y1) * b), fill=color, width=4)
    else:
        draw.line((x1, y1, x2, y2), fill=color, width=5)
    draw.polygon([(x2, y2), (x2 - 16, y2 - 9), (x2 - 16, y2 + 9)], fill=color)


def main():
    OUT.mkdir(exist_ok=True)
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    centered(draw, (W / 2, 52), "Living Tapestries Production Workflow", font(34, True), INK)
    centered(draw, (W / 2, 95), "Solid arrows: normal flow   Dashed arrows: hard-gate retries", font(22), (90, 96, 102))

    left, top = 55, 230
    node_w, node_h, gap = 205, 130, 30
    boxes = {}
    for i, (key, label) in enumerate(STAGES):
        x = left + i * (node_w + gap)
        y = top
        boxes[key] = (x, y, x + node_w, y + node_h)
        fill = (255, 248, 222) if key in {"qa", "review"} else (235, 243, 250)
        outline = GOLD if key in {"qa", "review"} else BLUE
        draw.rounded_rectangle(boxes[key], radius=18, fill=fill, outline=outline, width=5)
        centered(draw, (x + node_w / 2, y + node_h / 2), label.replace("\\n", "\n"), font(23, True), INK)

    for left_key, right_key, label in EDGES:
        if left_key not in boxes:
            continue
        if right_key == "end":
            continue
        a = boxes[left_key]
        b = boxes[right_key]
        retry = label.startswith("retry")
        color = RED if retry else BLUE
        if retry:
            y = top + node_h + 105
            draw.line((a[0] + node_w / 2, a[3], a[0] + node_w / 2, y), fill=color, width=4)
            draw.line((a[0] + node_w / 2, y, b[0] + node_w / 2, y), fill=color, width=4)
            arrow(draw, (b[0] + node_w / 2, y), (b[0] + node_w / 2, b[3]), color, dashed=True)
            centered(draw, ((a[0] + b[0] + node_w) / 2, y - 22), label.replace("retry: ", "retry: "), font(18, True), color)
        else:
            arrow(draw, (a[2] + 2, (a[1] + a[3]) / 2), (b[0] - 2, (b[1] + b[3]) / 2), color)
            centered(draw, ((a[2] + b[0]) / 2, a[1] - 24), label, font(16), (70, 76, 82))

    centered(draw, (W / 2, 720), "Narration waveform is the master clock; QA gates inspect the encoded film before Drive delivery.", font(24, True), INK)
    image.save(OUT / "production_workflow.png")
    image.save(OUT / "production_workflow.pdf", "PDF", resolution=150.0)


if __name__ == "__main__":
    main()
