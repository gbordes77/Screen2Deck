import numpy as np
import easyocr
import torch
import logging
import time
from ..config import get_settings

logger = logging.getLogger(__name__)
S = get_settings()

# Global reader instance (initialized on first use)
_reader = None
_reader_initializing = False

def get_reader():
    """Get or initialize EasyOCR reader with proper model download handling."""
    global _reader, _reader_initializing
    
    if _reader is not None:
        return _reader
    
    if _reader_initializing:
        # Wait for another thread that's initializing
        logger.info("⏳ Waiting for EasyOCR model initialization by another process...")
        while _reader_initializing and _reader is None:
            time.sleep(1)
        return _reader
    
    try:
        _reader_initializing = True
        logger.info("📥 Initializing EasyOCR reader (first use - downloading models ~64MB)...")
        logger.info("⏳ This may take 2-3 minutes on first run. Please wait...")
        
        # Initialize reader with GPU if available
        _reader = easyocr.Reader(["en","fr","de","es"], gpu=torch.cuda.is_available())
        
        logger.info("✅ EasyOCR models ready! Subsequent OCR will be fast (3-5 seconds).")
        return _reader
    except Exception as e:
        logger.error(f"❌ Failed to initialize EasyOCR: {e}")
        raise
    finally:
        _reader_initializing = False

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
        img_rgb = np.stack([img]*3, axis=-1)
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
    mean_conf = float(sum(s["conf"] for s in spans)/max(1,len(spans))) if spans else 0.0
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
    """Use OpenAI Vision API as fallback when EasyOCR fails."""
    import os
    from openai import OpenAI
    import cv2
    import base64
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "TO_BE_SET":
        logger.warning("OpenAI API key not configured, falling back to EasyOCR")
        return run_easyocr(img)
    
    try:
        client = OpenAI(api_key=api_key)
        
        # Convert image to base64
        _, buffer = cv2.imencode('.jpg', img)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        
        # Call OpenAI Vision API
        response = client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """Extract ALL Magic: The Gathering cards from this image.
                            Return ONLY the card names and quantities in this format:
                            4 Lightning Bolt
                            2 Counterspell
                            
                            For MTGA format where quantities appear as 'x2' below card names, combine them.
                            Include EVERY card you can see, including basic lands.
                            Separate mainboard and sideboard with the word 'Sideboard' on its own line."""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_base64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=4000
        )
        
        content = response.choices[0].message.content
        if not content:
            return run_easyocr(img)
        
        # Parse OpenAI response into our format
        spans = []
        for line in content.split('\n'):
            line = line.strip()
            if line:
                spans.append({"text": line, "conf": 0.95})  # High confidence for OpenAI
        
        mean_conf = 0.95 if spans else 0.0
        logger.info(f"✅ OpenAI Vision detected {len(spans)} text spans")
        return {"spans": spans, "mean_conf": mean_conf}
        
    except Exception as e:
        logger.error(f"OpenAI Vision API error: {e}")
        return run_easyocr(img)