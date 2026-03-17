"""Image preprocessing for better OCR results."""

import cv2
import numpy as np
from PIL import Image


def preprocess_image(image: Image.Image) -> Image.Image:
    """Apply preprocessing to improve OCR accuracy.

    Pipeline: convert to RGB -> upscale small images -> grayscale -> denoise -> threshold -> deskew
    """
    # Ensure image is in RGB mode (handles palette 'P', RGBA, LA, etc.)
    if image.mode != "RGB":
        image = image.convert("RGB")

    # Convert PIL to OpenCV
    img_array = np.array(image)

    # Upscale small images so Tesseract gets enough resolution
    h, w = img_array.shape[:2]
    if max(h, w) < 1500:
        scale = 1500 / max(h, w)
        img_array = cv2.resize(
            img_array, None, fx=scale, fy=scale,
            interpolation=cv2.INTER_CUBIC,
        )

    # Convert to grayscale if needed
    if len(img_array.shape) == 3:
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_array

    # Light denoise (h=7 preserves thin strokes better than h=10)
    denoised = cv2.fastNlMeansDenoising(gray, h=7)

    # Adaptive threshold – lower C value preserves lighter text
    thresh = cv2.adaptiveThreshold(
        denoised, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=21,
        C=4,
    )

    # Deskew if needed
    corrected = _deskew(thresh)

    return Image.fromarray(corrected)


def _deskew(image: np.ndarray) -> np.ndarray:
    """Correct skew in a binary image.

    Uses Hough line detection for more reliable angle estimation
    across all OpenCV versions (minAreaRect angle semantics changed
    in OpenCV 4.5.1+).
    """
    # Detect edges and find lines
    edges = cv2.Canny(image, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180,
        threshold=100, minLineLength=80, maxLineGap=10,
    )
    if lines is None or len(lines) < 5:
        return image

    # Compute median angle of detected lines
    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        dx = x2 - x1
        dy = y2 - y1
        if abs(dx) < 1:
            continue
        angle = np.degrees(np.arctan2(dy, dx))
        # Only consider near-horizontal lines (likely text baselines)
        if abs(angle) < 15:
            angles.append(angle)

    if not angles:
        return image

    median_angle = float(np.median(angles))

    # Only correct if skew is significant but not too extreme
    if abs(median_angle) < 0.5 or abs(median_angle) > 10:
        return image

    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    rotated = cv2.warpAffine(
        image, matrix, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )

    return rotated
