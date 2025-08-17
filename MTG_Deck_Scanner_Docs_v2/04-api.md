# REST API

## POST `/api/ocr/upload`
- **Body**: `multipart/form-data` with `file` (image)
- **Return**: `{ "jobId": "uuid" }`
- **Errors**: 400 `BAD_IMAGE`, 413 `BAD_IMAGE`, 429 `RATE_LIMIT`

## GET `/api/ocr/status/{jobId}`
- **Return**: 
```json
{
  "state": "queued|processing|completed|failed",
  "progress": 100,
  "result": {
    "jobId": "...",
    "raw": {"spans":[{"text":"...", "conf":0.92}], "mean_conf":0.87},
    "parsed": {"main":[{"qty":4,"name":"...","candidates":[...]}], "side":[...]} ,
    "normalized": {"main":[{"qty":4,"name":"Canon Name","scryfall_id":"..."}], "side":[...]},
    "timings_ms": {"total": 1320},
    "traceId": "..."
  },
  "error": null
}
```

## POST `/api/export/{target}`
- **Path param** `target`: `mtga | moxfield | archidekt | tappedout`
- **Body**: `NormalizedDeck`
- **Return**: `{ "text": "<export content>" }`
