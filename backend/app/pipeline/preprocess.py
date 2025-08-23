import cv2, numpy as np
from ..config import get_settings

S = get_settings()

def _unsharp_mask(img):
    blurred = cv2.GaussianBlur(img, (0,0), 1.0)
    return cv2.addWeighted(img, 1.5, blurred, -0.5, 0)

def _deskew(gray):
    coords = np.column_stack(np.where(gray > 0))
    if coords.shape[0] < 10: return gray
    angle = cv2.minAreaRect(coords)[-1]
    angle = -(90 + angle) if angle < -45 else -angle
    (h, w) = gray.shape[:2]
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

def _apply_clahe(gray):
    """Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)"""
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
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
    if scale < 1.0: scale = 1.0
    bgr = cv2.resize(bgr, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    
    # Apply CLAHE for better contrast (from reference project)
    gray = _apply_clahe(gray)
    
    gray = _unsharp_mask(gray)
    gray = cv2.fastNlMeansDenoising(gray, None, 8, 7, 21)
    th = cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,31,5)
    th = _deskew(th)
    return th

def preprocess_variants(bgr):
    """Generate multiple preprocessing variants for better OCR coverage"""
    variants = []
    
    # Convert to grayscale once
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    
    h, w = bgr.shape[:2]
    
    # Apply super-resolution if image is small
    if S.ENABLE_SUPERRES and w < S.SUPERRES_MIN_WIDTH:
        # Calculate scale needed to reach minimum width
        scale_factor = max(4, int(S.SUPERRES_MIN_WIDTH / w) + 1)
        bgr = _apply_super_resolution(bgr, scale=scale_factor)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY) if len(bgr.shape) == 3 else bgr
        h, w = bgr.shape[:2]
    
    # Variant 1: Original (for clean images)
    scale = 1500.0 / max(1.0, float(h))
    if scale < 1.0: scale = 1.0
    scaled = cv2.resize(bgr, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_CUBIC)
    variants.append(scaled)
    
    # Variant 2: CLAHE enhanced (from reference project - works well for low contrast)
    gray_scaled = cv2.resize(gray, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_CUBIC)
    clahe_img = _apply_clahe(gray_scaled)
    # Convert back to BGR for EasyOCR
    clahe_bgr = cv2.cvtColor(clahe_img, cv2.COLOR_GRAY2BGR)
    variants.append(clahe_bgr)
    
    # Variant 3: Denoised + Sharpened
    denoised = cv2.fastNlMeansDenoising(gray_scaled, None, 8, 7, 21)
    sharpened = _unsharp_mask(denoised)
    sharp_bgr = cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)
    variants.append(sharp_bgr)
    
    # Variant 4: Adaptive threshold (for very poor quality)
    th = cv2.adaptiveThreshold(gray_scaled, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 5)
    th_bgr = cv2.cvtColor(th, cv2.COLOR_GRAY2BGR)
    variants.append(th_bgr)
    
    return variants