import logging
import threading

import numpy as np
import easyocr
import torch

from ..config import get_settings
from .vision_providers import run_vision_chain

logger = logging.getLogger(__name__)
S = get_settings()

# Global reader instance (initialized on first use) guarded by a real
# threading.Lock to avoid the TOCTOU race of the previous busy-wait.
_reader = None
_reader_lock = threading.Lock()


def get_reader():
    """Get or initialize the EasyOCR reader in a thread-safe way."""
    global _reader

    if _reader is not None:
        return _reader

    with _reader_lock:
        if _reader is not None:
            return _reader
        logger.info(
            "📥 Initializing EasyOCR reader (first use - downloading models ~64MB)..."
        )
        logger.info("⏳ This may take 2-3 minutes on first run. Please wait...")
        try:
            _reader = easyocr.Reader(
                ["en", "fr", "de", "es"],
                gpu=torch.cuda.is_available(),
            )
            logger.info(
                "✅ EasyOCR models ready! Subsequent OCR will be fast (3-5 seconds)."
            )
            return _reader
        except Exception as e:
            logger.error("❌ Failed to initialize EasyOCR: %s", e)
            raise


def run_easyocr(img: np.ndarray, min_confidence: float = 0.3):
    """Run EasyOCR with confidence filtering.

    Args:
        img: Input image (grayscale or BGR)
        min_confidence: Minimum confidence threshold (default 0.3 from reference project)

    Returns:
        OCR results with filtered spans
    """
    # Get reader (will wait for model download if needed)
    reader = get_reader()

    if len(img.shape) == 2:
        img_rgb = np.stack([img] * 3, axis=-1)
    else:
        img_rgb = img

    results = reader.readtext(img_rgb, detail=1, paragraph=False)

    # Filter by confidence (from reference project)
    # Lower threshold (0.3) keeps more potential cards rather than missing them
    spans = []
    for (*_, text, conf) in results:
        if conf >= min_confidence:
            spans.append({"text": text, "conf": float(conf)})

    # Calculate mean confidence only from filtered spans
    mean_conf = (
        float(sum(s["conf"] for s in spans) / max(1, len(spans))) if spans else 0.0
    )
    return {"spans": spans, "mean_conf": mean_conf}


def run_easyocr_best_of(images, confidence_threshold=None, min_confidence=None):
    """Run OCR on multiple image variants with early termination on high confidence.

    Args:
        images: List of preprocessed image variants
        confidence_threshold: Stop processing if confidence exceeds this (default from config)
        min_confidence: Minimum confidence for individual text spans (default from config)

    Returns:
        Best OCR result found (most text detected with best confidence)
    """
    # Use config defaults if not specified
    if confidence_threshold is None:
        confidence_threshold = S.OCR_EARLY_STOP_CONF
    if min_confidence is None:
        min_confidence = S.OCR_MIN_SPAN_CONF
    best = {"spans": [], "mean_conf": 0.0}
    best_text_count = 0

    for i, im in enumerate(images):
        out = run_easyocr(im, min_confidence=min_confidence)

        # Prefer results with more detected text AND good confidence
        # This helps catch more cards even if confidence is lower
        text_count = len(out["spans"])

        # Score based on both text count and confidence
        # Prioritize finding more cards over perfect confidence
        current_score = text_count * 0.6 + out["mean_conf"] * 40
        best_score = best_text_count * 0.6 + best["mean_conf"] * 40

        if current_score > best_score:
            best = out
            best_text_count = text_count

        # Early termination: stop if we found high-confidence result with enough text
        # But don't stop too early if we haven't found many cards yet
        if best["mean_conf"] >= confidence_threshold and best_text_count >= 20:
            break

    return best


def run_vision_fallback(img: np.ndarray):
    """Vision fallback dispatcher.

    Delegates to the configured VisionProvider chain (default
    Gemini → Claude). On a total failure, falls back to a fresh EasyOCR
    pass so the request never returns empty.
    """
    result = run_vision_chain(img)
    if result.get("spans"):
        return result
    logger.warning("Vision fallback chain returned nothing; using EasyOCR pass")
    return run_easyocr(img)
