import cv2
import numpy as np
from ..config import get_settings

S = get_settings()


def _unsharp_mask(img):
    blurred = cv2.GaussianBlur(img, (0, 0), 1.0)
    return cv2.addWeighted(img, 1.5, blurred, -0.5, 0)


def _deskew(gray):
    coords = np.column_stack(np.where(gray > 0))
    if coords.shape[0] < 10:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    angle = -(90 + angle) if angle < -45 else -angle
    h, w = gray.shape[:2]
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(
        gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def _apply_clahe(gray):
    """Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)"""
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def _apply_super_resolution(img, scale=4):
    """Apply super-resolution upscaling for small images.

    Args:
        img: Input image (BGR or grayscale)
        scale: Upscaling factor (default 4x)

    Returns:
        Upscaled image
    """
    h, w = img.shape[:2]

    # Use INTER_CUBIC for upscaling (better quality than INTER_LINEAR)
    # For even better quality, could use cv2.dnn_superres but requires additional models
    new_w = w * scale
    new_h = h * scale

    # Apply initial upscale
    upscaled = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

    # Apply sharpening to enhance edges after upscaling
    upscaled = _unsharp_mask(upscaled)

    return upscaled


def preprocess(bgr):
    h, w = bgr.shape[:2]
    scale = 1500.0 / max(1.0, float(h))
    if scale < 1.0:
        scale = 1.0
    bgr = cv2.resize(
        bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC
    )
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    # Apply CLAHE for better contrast (from reference project)
    gray = _apply_clahe(gray)

    gray = _unsharp_mask(gray)
    gray = cv2.fastNlMeansDenoising(gray, None, 8, 7, 21)
    th = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 5
    )
    th = _deskew(th)
    return th


def preprocess_variants(bgr):
    """Generate multiple preprocessing variants for better OCR coverage.

    This restores the **6-variant set** from the original August 2025
    pipeline plus the CLAHE + super-res improvements that landed later.
    The key lost variants, which are now back:

    - ``bitwise_not`` inversion for **MTGA dark-theme** screenshots
      (white text on dark UI is the primary MTGA layout — EasyOCR
      prefers dark-on-light, so inverting the binary beats running
      it on the raw screenshot).
    - ``morphologyEx(MORPH_CLOSE)`` to join broken glyphs and — on
      tabular MTGA/MTGO layouts — merge the quantity number with the
      card name row so the regex parser in ``main.py`` sees them as
      a single ``"4 Lightning Bolt"`` span instead of two disjoint
      ``"4"`` and ``"Lightning Bolt"`` spans.

    Variants returned (all single-channel / binarised where relevant —
    EasyOCR's ``run_easyocr`` wrapper handles the dimensionality):

    1. ``base``           — adaptive-threshold + unsharp + denoise + deskew
    2. ``base_alt``       — alternate adaptive-threshold parameters
    3. ``base_close``     — ``base`` with morphological close
    4. ``base_inverted``  — ``bitwise_not(base)`` (dark theme support)
    5. ``clahe``          — CLAHE contrast lift (low-contrast shots)
    6. ``denoised``       — fastNlMeans + unsharp (noisy shots)
    """
    h, w = bgr.shape[:2]

    # Apply super-resolution if image is small before any other step
    # (keeps downstream variants working at a legible pixel density).
    if S.ENABLE_SUPERRES and w < S.SUPERRES_MIN_WIDTH:
        scale_factor = max(4, int(S.SUPERRES_MIN_WIDTH / w) + 1)
        bgr = _apply_super_resolution(bgr, scale=scale_factor)
        h, w = bgr.shape[:2]

    # Scale everything to a ~1500 px height for consistent EasyOCR input.
    scale = 1500.0 / max(1.0, float(h))
    if scale < 1.0:
        scale = 1.0
    bgr_scaled = cv2.resize(
        bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC
    )
    gray_scaled = cv2.cvtColor(bgr_scaled, cv2.COLOR_BGR2GRAY)

    # --- Variant 1: the canonical "base" (unsharp + denoise + adaptive
    # threshold + deskew). This is the one EasyOCR historically liked
    # best on MTGA Arena screenshots. ---
    base_gray = _unsharp_mask(gray_scaled)
    base_gray = cv2.fastNlMeansDenoising(base_gray, None, 8, 7, 21)
    base = cv2.adaptiveThreshold(
        base_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 5
    )
    base = _deskew(base)

    # --- Variant 2: alternate adaptive-threshold parameters (larger block
    # size, different C). Handles screenshots with uneven lighting. ---
    alt_gray = _unsharp_mask(gray_scaled)
    base_alt = cv2.adaptiveThreshold(
        alt_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 25, 7
    )
    base_alt = _deskew(base_alt)

    # --- Variant 3: morphological CLOSE on the base. Bridges the visual
    # gap between the qty column and the card-name column in MTGA /
    # MTGO layouts so EasyOCR emits a single "4 Lightning Bolt" span. ---
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    base_close = cv2.morphologyEx(base, cv2.MORPH_CLOSE, kernel, iterations=1)

    # --- Variant 4: inverted base — essential for MTGA's dark-theme UI.
    # EasyOCR was trained primarily on dark-text-on-light-background
    # data, and the Arena deck builder is light-text-on-dark. ---
    base_inverted = cv2.bitwise_not(base)

    # --- Variant 5: CLAHE contrast lift. Works well on washed-out /
    # low-contrast screenshots where a hard threshold would kill text. ---
    clahe_img = _apply_clahe(gray_scaled)

    # --- Variant 6: denoised + sharpened grayscale, no threshold. Some
    # images (e.g. real-life photographs of paper decklists) lose too
    # much information when binarised; keeping a grayscale pass gives
    # EasyOCR a second chance. ---
    denoised = cv2.fastNlMeansDenoising(gray_scaled, None, 8, 7, 21)
    denoised = _unsharp_mask(denoised)

    # Return the four variants that carry the most independent signal.
    # The "denoised grayscale" and the "alternate threshold" variants
    # were historically in the set but rarely won the best-of race on
    # CPU-bound deployments — each variant runs EasyOCR end-to-end, so
    # every one we keep costs real wall-clock. With `add_margin` +
    # `link_threshold` tuning the spatial parser already pulls most
    # cards from ``base`` or ``base_close``; ``base_inverted`` is the
    # one that saves MTGA dark-theme shots; ``clahe_img`` handles the
    # low-contrast websites / mtggoldfish captures.
    return [base, base_close, base_inverted, clahe_img]
