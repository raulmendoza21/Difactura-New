"""Image preprocessing for better OCR results."""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image


def preprocess_image(image: Image.Image) -> Image.Image:
    """Return the default OCR preprocessing variant."""
    return build_ocr_variants(image)[0]["image"]


def build_ocr_variants(image: Image.Image, input_kind: str = "image_scan") -> list[dict]:
    """Build multiple OCR-oriented variants and let the OCR layer choose."""
    rgb_image = image.convert("RGB") if image.mode != "RGB" else image
    img_array = np.array(rgb_image)

    base_steps: list[str] = []
    height, width = img_array.shape[:2]
    max_side_limit = 1700 if input_kind == "image_photo" else 2200
    if max(height, width) > max_side_limit:
        scale = max_side_limit / max(height, width)
        img_array = cv2.resize(
            img_array,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_AREA,
        )
        if input_kind == "image_photo":
            base_steps.append("downscale_mobile_photo")
        else:
            base_steps.append("downscale_large_image")

    variants: list[dict] = []

    def add_variant(name: str, array: np.ndarray, steps: list[str]) -> None:
        variants.append(
            {
                "name": name,
                "image": Image.fromarray(array),
                "preprocessing_steps": [*steps, f"ocr_variant:{name}"],
            }
        )

    image_sources: list[tuple[str, np.ndarray, list[str]]] = []
    if input_kind == "image_photo":
        cropped_image, document_steps = _extract_document_region(img_array)
        if document_steps:
            image_sources.append(("document", cropped_image, [*base_steps, *document_steps]))
        else:
            image_sources.append(("full", img_array, [*base_steps]))
    else:
        image_sources.append(("base", img_array, [*base_steps]))

    for source_name, source_image, source_steps in image_sources:
        working_image = source_image
        source_height, source_width = working_image.shape[:2]
        source_base_steps = [*source_steps]

        upscale_target = 1300 if input_kind == "image_photo" else 1500
        if max(source_height, source_width) < upscale_target:
            scale = upscale_target / max(source_height, source_width)
            working_image = cv2.resize(
                working_image,
                None,
                fx=scale,
                fy=scale,
                interpolation=cv2.INTER_CUBIC,
            )
            source_base_steps.append("upscale_small_image")

        gray = cv2.cvtColor(working_image, cv2.COLOR_RGB2GRAY)
        denoised = cv2.fastNlMeansDenoising(gray, h=7)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(gray)

        if input_kind == "image_photo":
            blurred = cv2.GaussianBlur(gray, (0, 0), 2.2)
            unsharp = cv2.addWeighted(gray, 1.6, blurred, -0.6, 0)
            photo_binary = cv2.adaptiveThreshold(
                unsharp,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                blockSize=31,
                C=8,
            )
            add_variant(
                f"{source_name}_photo_enhanced",
                _deskew(photo_binary),
                [*source_base_steps, "grayscale", "unsharp_mask", "adaptive_threshold", "deskew"],
            )

            add_variant(
                f"{source_name}_clahe_gray",
                clahe,
                [*source_base_steps, "grayscale", "clahe"],
            )
            continue

        balanced_binary = cv2.adaptiveThreshold(
            denoised,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=21,
            C=4,
        )
        add_variant(
            f"{source_name}_balanced_binary",
            _deskew(balanced_binary),
            [*source_base_steps, "grayscale", "denoise", "adaptive_threshold", "deskew"],
        )

        contrast_binary = cv2.adaptiveThreshold(
            clahe,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=25,
            C=6,
        )
        add_variant(
            f"{source_name}_contrast_binary",
            _deskew(contrast_binary),
            [*source_base_steps, "grayscale", "clahe", "adaptive_threshold", "deskew"],
        )

        if input_kind == "pdf_scanned":
            blurred = cv2.GaussianBlur(gray, (0, 0), 2.2)
            unsharp = cv2.addWeighted(gray, 1.6, blurred, -0.6, 0)
            photo_binary = cv2.adaptiveThreshold(
                unsharp,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                blockSize=31,
                C=8,
            )
            add_variant(
                f"{source_name}_photo_enhanced",
                _deskew(photo_binary),
                [*source_base_steps, "grayscale", "unsharp_mask", "adaptive_threshold", "deskew"],
            )

            # Keep one softer path for scanned paper in case thresholding destroys text.
            add_variant(
                f"{source_name}_clahe_gray",
                clahe,
                [*source_base_steps, "grayscale", "clahe"],
            )
        else:
            _, otsu_binary = cv2.threshold(
                denoised,
                0,
                255,
                cv2.THRESH_BINARY + cv2.THRESH_OTSU,
            )
            add_variant(
                f"{source_name}_scan_otsu",
                _deskew(otsu_binary),
                [*source_base_steps, "grayscale", "denoise", "otsu_threshold", "deskew"],
            )

    return variants


def _extract_document_region(image: np.ndarray) -> tuple[np.ndarray, list[str]]:
    """Detect and rectify the paper document inside a mobile photo."""
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 180)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(closed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    image_area = float(image.shape[0] * image.shape[1])

    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:10]:
        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 0:
            continue

        approximation = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        area = cv2.contourArea(approximation)
        if len(approximation) != 4 or area < image_area * 0.2:
            continue

        ordered_points = _order_points(approximation.reshape(4, 2).astype("float32"))
        warped = _four_point_transform(image, ordered_points)
        if min(warped.shape[:2]) < 400:
            continue

        trimmed = _trim_document_margins(warped)
        return trimmed, ["document_contour_detected", "perspective_corrected", "document_cropped"]

    return image, []


def _deskew(image: np.ndarray) -> np.ndarray:
    """Correct skew in a binary image."""
    edges = cv2.Canny(image, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180,
        threshold=100,
        minLineLength=80,
        maxLineGap=10,
    )
    if lines is None or len(lines) < 5:
        return image

    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        dx = x2 - x1
        dy = y2 - y1
        if abs(dx) < 1:
            continue
        angle = np.degrees(np.arctan2(dy, dx))
        if abs(angle) < 15:
            angles.append(angle)

    if not angles:
        return image

    median_angle = float(np.median(angles))
    if abs(median_angle) < 0.5 or abs(median_angle) > 10:
        return image

    height, width = image.shape[:2]
    center = (width // 2, height // 2)
    matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    return cv2.warpAffine(
        image,
        matrix,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def _order_points(points: np.ndarray) -> np.ndarray:
    """Return points ordered as top-left, top-right, bottom-right, bottom-left."""
    ordered = np.zeros((4, 2), dtype="float32")
    point_sums = points.sum(axis=1)
    point_diffs = np.diff(points, axis=1)

    ordered[0] = points[np.argmin(point_sums)]
    ordered[2] = points[np.argmax(point_sums)]
    ordered[1] = points[np.argmin(point_diffs)]
    ordered[3] = points[np.argmax(point_diffs)]
    return ordered


def _four_point_transform(image: np.ndarray, points: np.ndarray) -> np.ndarray:
    """Warp the image so the detected document becomes front-facing."""
    top_left, top_right, bottom_right, bottom_left = points

    width_a = np.linalg.norm(bottom_right - bottom_left)
    width_b = np.linalg.norm(top_right - top_left)
    max_width = max(int(width_a), int(width_b))

    height_a = np.linalg.norm(top_right - bottom_right)
    height_b = np.linalg.norm(top_left - bottom_left)
    max_height = max(int(height_a), int(height_b))

    if max_width < 1 or max_height < 1:
        return image

    destination = np.array(
        [
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1],
        ],
        dtype="float32",
    )

    matrix = cv2.getPerspectiveTransform(points, destination)
    return cv2.warpPerspective(image, matrix, (max_width, max_height))


def _trim_document_margins(image: np.ndarray) -> np.ndarray:
    """Remove a thin border after the perspective transform."""
    height, width = image.shape[:2]
    margin_y = max(4, int(height * 0.015))
    margin_x = max(4, int(width * 0.015))

    if height <= margin_y * 2 or width <= margin_x * 2:
        return image

    return image[margin_y : height - margin_y, margin_x : width - margin_x]
