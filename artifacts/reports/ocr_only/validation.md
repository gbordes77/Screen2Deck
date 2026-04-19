# OCR-only validation report

- **Date**: 2026-04-18T01:56:13
- **Git SHA**: `0ef8797`
- **Backend**: `http://localhost:8080`
- **Images tested**: 10
- **Completed**: 8
- **Failed / timed out**: 2

## Latency (client-side, full round-trip)

- mean: **251490.8 ms**
- median: **228233.7 ms**
- p95: **413515.9 ms**
- min / max: 157608.3 / 413515.9 ms

## Accuracy vs truth files

- exact-match mean: **0.0 %**
- fuzzy-match mean (>=0.88 similarity): **0.0 %**

## Per-image results

| Image | Resolution | State | Total (ms) | Mean conf | Main | Side | Exact % | Fuzzy % |
|---|---|---|---|---|---|---|---|---|
| MTGA deck list 4_1920x1080.jpeg | 1920x1080 | completed | 247814 | 0.77 | 2 / 0 | 1 / 0 | — | — |
| MTGA deck list special_1334x886.jpeg | 1334x886 | completed | 338047 | 0.76 | 0 / 0 | 1 / 0 | — | — |
| MTGA deck list_1535x728.jpeg | 1535x728 | completed | 217528 | 0.78 | 0 / 17 | 1 / 8 | 0.0 | 0.0 |
| MTGO deck list not usual_2336x1098.jpeg | 2336x1098 | completed | 222621 | 0.79 | 0 / 0 | 1 / 0 | — | — |
| MTGO deck list usual 4_1254x432.jpeg | 1254x432 | completed | 180945 | 0.71 | 0 / 0 | 4 / 0 | — | — |
| MTGO deck list usual_1763x791.jpeg | 1763x791 | completed | 233846 | 0.74 | 1 / 21 | 0 / 8 | 0.0 | 0.0 |
| image_677x309.webp | 677x309 | completed | 157608 | 0.72 | 0 / 0 | 0 / 0 | — | — |
| mtggoldfish deck list 10_1239x1362.jpg | 1239x1362 | completed | 413515 | 0.63 | 1 / 0 | 0 / 0 | — | — |
| real deck cartes cachés_2048x1542.jpeg | 2048x1542 | error | 0 | 0.00 | 0 / 0 | 0 / 0 | — | — |
| web site  deck list_2300x2210.jpeg | 2300x2210 | error | 0 | 0.00 | 0 / 0 | 0 / 0 | — | — |

## How to reproduce

```bash
# 1. put the backend in full-OCR mode (no AI calls at all):
ENABLE_VISION_FALLBACK=false docker compose up -d --force-recreate backend

# 2. once /health returns 200, run the harness:
make bench-ocr-only
# equivalent to:
#   python tools/ocr_only_bench.py \
#     --images validation_set/images --truth validation_set/truth \
#     --out artifacts/reports/ocr_only
```

## Notes

- This harness is designed to be invoked with the backend running in
  full-OCR mode (`ENABLE_VISION_FALLBACK=false`). Any LLM call at that
  point indicates a misconfigured deployment, not a failure of the
  harness itself.
- `Main` and `Side` columns show `detected / truth`. A `—` in the
  accuracy columns means no truth file was supplied for that image.
- `Mean conf` comes from EasyOCR's post-filter mean span confidence.
- Per-image latency is dominated by EasyOCR on CPU (no GPU in this
  container). Expect roughly 10-30× faster numbers on a CUDA-enabled
  deployment — this is a reproducibility report, not a performance claim.
- The regex parser in `backend/app/main.py::parse_deck_sections` expects
  each OCR span to contain both the quantity and the card name on the
  same line (e.g. `"4 Lightning Bolt"`). When a screenshot's layout
  causes EasyOCR to emit the qty and the name as *separate* spans,
  the parser drops both; this shows up as a low `Main` / `Side` count
  even when `Mean conf` is healthy. The AI-backup path exists precisely
  to rescue those layouts — hence `ENABLE_VISION_FALLBACK=true` in the
  canonical deployment.
