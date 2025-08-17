# Validation Plan

## Dataset
- ≥20 images total: MTGA, MTGO, web exports, IRL photos at different resolutions.

## Metrics
- **Deck accuracy**: % of (name + qty + section) correct.
- OCR CER/WER (informative only).
- Latency p95 (total pipeline).

## Procedure
1. Put images in `validation_set/`.
2. Start backend & webapp.
3. Run `backend/tests/test_validation_set.py` and collect timings.

## Targets
- Deck accuracy ≥ 95%
- Latency p95 ≤ 5–8s (warm/cold)
- 100% export conformance (golden tests later)
