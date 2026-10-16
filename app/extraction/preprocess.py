"""app/extraction/preprocess.py – OpenCV image preprocessing for receipts.

Pipeline:
  1. Decode image bytes to numpy array
  2. Convert to grayscale
  3. Deskew (estimate skew angle from Hough lines, rotate)
  4. CLAHE contrast enhancement
  5. Resize so longest side <= 2000 px
  6. Re-encode as JPEG

Any step failure falls back to the original image bytes.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)

MAX_SIDE = 2000


def preprocess_image(image_bytes: bytes) -> bytes:
    """Preprocess a receipt image for LLM extraction.

    Args:
        image_bytes: raw image bytes (JPEG, PNG, WebP, etc.)

    Returns:
        Preprocessed image as JPEG bytes. Falls back to original on error.
    """
    try:
        return _preprocess(image_bytes)
    except Exception as exc:
        logger.warning("Image preprocessing failed, using original: %s", exc)
        return image_bytes


def _preprocess(image_bytes: bytes) -> bytes:
    # Decode
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("cv2.imdecode returned None")

    # Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Deskew
    gray = _deskew(gray)

    # CLAHE contrast
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # Resize so longest side <= MAX_SIDE
    h, w = enhanced.shape[:2]
    longest = max(h, w)
    if longest > MAX_SIDE:
        scale = MAX_SIDE / longest
        new_w = int(w * scale)
        new_h = int(h * scale)
        enhanced = cv2.resize(enhanced, (new_w, new_h), interpolation=cv2.INTER_AREA)

    # Re-encode as JPEG
    success, buf = cv2.imencode(".jpg", enhanced, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not success:
        raise ValueError("cv2.imencode failed")
    return bytes(buf)


def _deskew(gray: np.ndarray) -> np.ndarray:
    """Estimate skew angle and rotate the image to correct it."""
    try:
        # Edge detection
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        # Hough line transform
        lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=100)
        if lines is None or len(lines) == 0:
            return gray

        angles = []
        for line in lines[:50]:  # limit to 50 most prominent lines
            rho, theta = line[0]
            # theta near 0 or pi means horizontal line; convert to degrees
            angle_deg = np.degrees(theta) - 90
            if -45 < angle_deg < 45:
                angles.append(angle_deg)

        if not angles:
            return gray

        median_angle = float(np.median(angles))
        if abs(median_angle) < 0.5:
            return gray  # no meaningful skew

        # Rotate
        h, w = gray.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        rotated = cv2.warpAffine(
            gray,
            M,
            (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )
        return rotated
    except Exception as exc:
        logger.debug("Deskew failed: %s", exc)
        return gray
