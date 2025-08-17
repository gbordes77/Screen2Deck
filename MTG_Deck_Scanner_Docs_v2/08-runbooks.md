# Runbooks

## OCR quality issues
- Ensure preprocess variants enabled (default).
- Increase `OCR_MIN_LINES` or decrease `OCR_MIN_CONF` depending on false positives/negatives.
- Enable `ENABLE_VISION_FALLBACK=true` for tough photos.

## Scryfall offline cache missing
- Run `python backend/scripts/download_scryfall.py` or relaunch backend with internet.

## Scryfall online throttling
- Increase `SCRYFALL_API_RATE_LIMIT_MS` (e.g., 250–400ms).

## Latency > p95 target
- Disable `ENABLE_SUPERRES`.
- Reduce image max height to 1400–1500px.
- Profile timings in `result.timings_ms`.

## Body too large (413)
- Increase `MAX_IMAGE_MB` or compress screenshots before upload.

## CORS errors
- Restrict/allow origins in FastAPI CORS middleware; set to your frontend domain in prod.
