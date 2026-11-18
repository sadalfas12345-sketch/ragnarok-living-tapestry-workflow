from pathlib import Path
import cv2
import numpy as np


def repair(path: Path, boundaries=(1620, 3240), half_width=90) -> None:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(path)
    out = image.astype(np.float32)
    height, width = image.shape[:2]
    for boundary in boundaries:
        left = max(0, boundary - half_width)
        right = min(width, boundary + half_width)
        band = image[:, left:right]
        blurred = cv2.GaussianBlur(band, (0, 0), 13).astype(np.float32)
        alpha = np.abs(np.arange(left, right, dtype=np.float32) - boundary) / half_width
        alpha = np.clip((1.0 - alpha) * 0.78, 0.0, 0.78)[None, :, None]
        out[:, left:right] = out[:, left:right] * (1.0 - alpha) + blurred * alpha
    cv2.imwrite(str(path), np.clip(out, 0, 255).astype(np.uint8), [cv2.IMWRITE_PNG_COMPRESSION, 3])


if __name__ == "__main__":
    import sys
    for raw in sys.argv[1:]:
        repair(Path(raw))
