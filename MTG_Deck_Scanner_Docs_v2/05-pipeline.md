# Pipeline — OCR & Canonicalization

## Preprocess
- Resize to ~1500px height (no upscaling beyond that).
- Unsharp mask → Denoise (fastNlMeans).
- Adaptive threshold → Deskew.
- **Variants** (secondary thresholds, morphological close, inversion). Keep the OCR run with **highest mean confidence** and more `qty name` lines.

## OCR
- **Primary**: EasyOCR (`en,fr,de,es`).
- **Never** Tesseract.
- **Fallback** (flag): Vision OCR when `mean_conf < OCR_MIN_CONF` or too few qty-name lines.

## Parse
- Lines like `4 Card Name` and `4x Card Name`.
- `Sideboard`/`SB` split detection.

## Matching
- Fuzzy candidates via RapidFuzz + metaphone on local Scryfall corpus.

## Canonicalization (ALWAYS)
Every card name is resolved via **Scryfall**:
1. Offline exact (cache)
2. Offline fuzzy (score ≥ 85)
3. Online `/cards/named?fuzzy=` (if enabled)
4. Online autocomplete suggestions

Attach `scryfall_id`, keep candidate list for UI.
