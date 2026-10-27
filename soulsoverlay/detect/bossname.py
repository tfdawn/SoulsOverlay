"""Boss name OCR.

Boss names are light text over a busy background. We scale the strip to a
fixed height, keep the bright low-saturation pixels (the lettering), and hand
Tesseract a single text line. The raw text is then fuzzy-matched against the game's boss list, which
absorbs most OCR mistakes ("Fel Omen" still finds "Margit, the Fell Omen").
"""

from __future__ import annotations

import os
import shutil

import cv2
import numpy as np

from . import crop

try:
    import pytesseract
except ImportError:  # pragma: no cover
    pytesseract = None


class OcrUnavailable(RuntimeError):
    pass


def configure(tesseract_cmd: str = ""):
    if pytesseract is None:
        raise OcrUnavailable("pytesseract is not installed")
    from ..app import bundled_tesseract

    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    elif bundled := bundled_tesseract():
        # The copy packed into SoulsOverlay.exe, with its own language data.
        pytesseract.pytesseract.tesseract_cmd = str(bundled)
        os.environ.setdefault("TESSDATA_PREFIX", str(bundled.parent / "tessdata"))
    elif not shutil.which("tesseract"):
        # Default install location of the UB Mannheim Windows build.
        candidate = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        pytesseract.pytesseract.tesseract_cmd = candidate


def preprocess(img: np.ndarray, cfg: dict) -> np.ndarray:
    """Binarise the name strip: bright, low-saturation pixels are lettering.

    A fixed brightness/saturation cut beats Otsu here: behind the name there
    is often bright but saturated scenery (gold leaves, fire) that Otsu would
    lump in with the text. The strip is first scaled to a fixed height so the
    same thresholds work whatever resolution OBS hands us.
    """
    target = cfg.get("target_height", 56)
    scale = target / max(1, img.shape[0])
    if abs(scale - 1.0) > 0.05:
        interp = cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=interp)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    text = (hsv[..., 2] >= cfg.get("text_v_min", 150)) & (hsv[..., 1] <= cfg.get("text_s_max", 80))
    binary = np.where(text, 0, 255).astype(np.uint8)  # dark text on white for Tesseract
    return cv2.copyMakeBorder(binary, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255)


def read_name(frame: np.ndarray, region, ocr_cfg: dict) -> str:
    roi = crop(frame, region)
    if roi is None or pytesseract is None:
        return ""
    # Skip OCR on an empty strip: no bright pixels means no name on screen.
    if cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY).max() < 120:
        return ""
    img = preprocess(roi, ocr_cfg)
    try:
        text = pytesseract.image_to_string(img, config=f"--psm {ocr_cfg.get('psm', 7)}")
    except pytesseract.TesseractNotFoundError as e:
        raise OcrUnavailable(str(e)) from e
    return " ".join(text.split())
