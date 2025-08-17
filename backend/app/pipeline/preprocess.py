import cv2, numpy as np

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

def preprocess(bgr):
    h, w = bgr.shape[:2]
    scale = 1500.0 / max(1.0, float(h))
    if scale < 1.0: scale = 1.0
    bgr = cv2.resize(bgr, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = _unsharp_mask(gray)
    gray = cv2.fastNlMeansDenoising(gray, None, 8, 7, 21)
    th = cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,31,5)
    th = _deskew(th)
    return th

def preprocess_variants(bgr):
    base = preprocess(bgr)
    variants = [base]
    # autre paramétrage
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = _unsharp_mask(gray)
    th2 = cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,25,7)
    th2 = _deskew(th2); variants.append(th2)
    # fermeture morpho
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (2,2))
    close = cv2.morphologyEx(base, cv2.MORPH_CLOSE, k, iterations=1)
    variants.append(close)
    # inversion (thèmes sombres)
    variants.append(cv2.bitwise_not(base))
    return variants