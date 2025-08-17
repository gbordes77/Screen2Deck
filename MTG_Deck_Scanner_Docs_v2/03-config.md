# Configuration & Flags

Backend `.env` keys:

| Key | Default | Meaning |
|---|---|---|
| `APP_ENV` | `dev` | Environment name |
| `PORT` | `8080` | Backend HTTP port |
| `LOG_LEVEL` | `INFO` | Logging level |
| `ENABLE_VISION_FALLBACK` | `false` | Allow fallback OCR provider |
| `ENABLE_SUPERRES` | `false` | Enable super-resolution step (slower) |
| `OCR_MIN_CONF` | `0.62` | Mean confidence threshold hint |
| `OCR_MIN_LINES` | `10` | Min lines like `qty name` before fallback |
| `ALWAYS_VERIFY_SCRYFALL` | `true` | Always canonicalize names via Scryfall |
| `ENABLE_SCRYFALL_ONLINE_FALLBACK` | `true` | Allow online Scryfall API calls |
| `SCRYFALL_API_TIMEOUT` | `5` | Timeout (s) for Scryfall API |
| `SCRYFALL_API_RATE_LIMIT_MS` | `120` | Client-side pacing between API requests |
| `SCRYFALL_DB` | `./app/data/scryfall_cache.sqlite` | SQLite path for cache |
| `SCRYFALL_BULK_PATH` | `./app/data/scryfall-default-cards.json` | Bulk JSON path |
| `SCRYFALL_TIMEOUT` | `5` | Timeout for bulk metadata list |
| `MAX_IMAGE_MB` | `8` | Max upload size |
| `FUZZY_MATCH_TOPK` | `5` | Size of suggestion list |
| `USE_REDIS` | `false` | (optional) use Redis for jobs/limits |
| `REDIS_URL` | `redis://redis:6379/0` | Redis DSN |

Webapp `.env.local`:
- `NEXT_PUBLIC_API_BASE` — default `http://localhost:8080`
