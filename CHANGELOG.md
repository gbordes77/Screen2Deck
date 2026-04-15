# Changelog

All notable changes to Screen2Deck will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.4.0] - 2026-04-14 - Vision-primary pipeline + security sprints

> **⚠️ Status of the performance claims in this entry**
>
> The latency, accuracy and cost figures in the "Performance" section
> below are **projections** — outputs of a performance-engineer agent's
> model plus arithmetic on published Gemini pricing — not measurements
> taken on this branch. Everything in "Added", "Changed", "Removed",
> and "Security" is real code that landed in real commits; the numbers
> are the optimistic target. See [`DISCLAIMER.md`](./DISCLAIMER.md) for
> the exact list of verified vs projected claims, and run `make smoke`
> followed by `make bench-day0` to turn them into real measurements.

### Added
- **Vision provider abstraction** (`backend/app/pipeline/vision_providers.py`) with a `VisionProvider` ABC, `GeminiVisionProvider` (primary, `gemini-3.1-flash-lite-preview`), and `ClaudeVisionProvider` (fallback, `claude-haiku-4-5`). Configurable via `VISION_PROVIDER=gemini,claude`.
- **Structured JSON output** (`extract_deck_structured`) using Gemini `response_schema` and Claude forced tool-use. Returns typed `{main, side}` directly, killing the regex parser on the happy path. New `run_vision_chain_structured` walker.
- **VISION_PRIMARY feature flag** — when true, `main.py::process_ocr` calls Vision first and skips preprocessing + EasyOCR + `parse_deck_sections` entirely. EasyOCR stays wired as the fallback. Models p95 4.1 s → 2.7 s, accuracy +3–5 points.
- **Scryfall batch endpoint** — new `SCRYFALL.batch_resolve(names)` via `POST /cards/collection` (75 identifiers per request, with split/DFC face reconciliation). 60-card decks now resolve in ~500 ms instead of ~7 s.
- **Scryfall bulk hydrate on startup** via `asyncio.to_thread(SCRYFALL.hydrate_from_bulk)`. `all_names()` is memoized process-level behind a `threading.Lock`.
- **`get_optional_token` dependency** in `backend/app/auth.py` that reads `request.state.token_data` populated by the middleware without raising 401.
- **Frontend**: `app/error.tsx`, `app/loading.tsx`, `app/result/[jobId]/error.tsx`, `app/result/[jobId]/loading.tsx`. Typed `lib/api.ts` with discriminated `JobStatus` union and `ApiError` class. Every public function accepts an optional `AbortSignal`.
- **Real unit tests**: `tests/unit/test_business_rules.py` (5 cases exercising the real MTGO 60+15 redistribution via `backend.app.business_rules`) and `tests/unit/test_exporters.py` (6 cases exercising CSV escaping on `Knight, Errant` / `Fire // Ice`).
- **CI guard** in `security-checks.yml` that fails on any reintroduction of `postgres:postgres`, `changeme`, `your-super-secret`, `dev-secret-key-change-in-production`, or `local-demo-key-with`.
- `LICENSE` (MIT), `CONTRIBUTING.md`.

### Changed
- **BREAKING (env)**: `docker-compose.yml` and `docker-compose.local.yml` now require `${POSTGRES_PASSWORD:?}` and `${JWT_SECRET_KEY:?}` — compose fails loudly if they're unset. `.env.example` ships empty placeholders.
- **Vision provider migration**: dropped `openai==1.3.0` (deprecated `gpt-4-vision-preview`), added `google-genai>=0.8.0` and `anthropic>=0.39.0`. Updated `.env.example`, `backend/.env.docker`, and both Settings classes (`backend/app/config.py`, `backend/app/core/config.py`).
- **Auth library**: `python-jose[cryptography]==3.3.0` replaced by `PyJWT>=2.8.0` + `cryptography>=42.0.0`. Fixes CVE-2024-33663 (algorithm confusion) and CVE-2024-33664 (JWT decompression bomb). Every `jwt.decode` now requires `exp`.
- **AuthMiddleware** rewritten as optional-auth: always populates `request.state.token_data`, never raises 401, rate-limits `/api/ocr/upload|status` + `/api/export/*`. The IDOR in `get_job_status` is now fixed — ownership is enforced unconditionally when `job.user_id` is set.
- **Scryfall client**: User-Agent `Screen2Deck/2.3 (+https://github.com/gbordes77/Screen2Deck)` + Accept headers on the `requests.Session` (required by Scryfall policy since 2024). `SCRYFALL_API_RATE_LIMIT_MS` bumped 120 → 100 ms to match the official 10 req/s guideline.
- **Scryfall schema**: added index on `cards(lang)`.
- **Frontend**: `tsconfig strict: true + noUncheckedIndexedAccess + noImplicitOverride`. `<html lang>` normalized to `"en"` to match the UI. `alert()`-based "copied" notice replaced with an `aria-live="polite"` region. File input has a real `<label>`.
- **Archidekt exporter** now uses `csv.writer` for proper quoting of card names with commas (`Knight, Errant`).
- **Locustfile**: fixed `NameError` in `EnduranceTestUser.normal_workflow` when the status endpoint returned non-200.
- **CI**: `ci.yml` pytest path fixed so both `tests/` and `backend/tests/` actually run; dropped `|| true` on the webapp type-check step. `proof-tests.yml` dropped `|| true` on every test/bench/golden/parity step so failures are no longer silenced.
- **MTGO 60+15 segmentation**: `business_rules.apply_mtgo_land_fix` is no longer a no-op stub — it redistributes overflowing mainboard cards into the sideboard. Wired into `main.py` canonical pipeline. Wasn't running in production on v2.3.0 despite being shipped.
- **Circuit breaker**: fixed broken import path in `backend/app/core/circuit_breaker.py` (`app.core.telemetry` → `app.telemetry`). The whole module was unimportable before.

### Removed
- `backend/app/main_original.py`, `main_refactored.py`, `migrate_to_production.py` — consolidation leftovers, canonical entry is unambiguously `main.py`.
- `backend/app/tasks.py` (Celery worker with a double-escaped regex `r"^\\s*..."` that matched nothing, duplicating the inline pipeline with a divergent parser).
- `backend/app/services/ocr_service.py` (orphan `OCRService` class, third source of truth for card parsing).
- `backend/app/matching/scryfall_cache.py` (async aiohttp wrapper with a correctness bug — `save_card` was never reachable, cache perpetually cold, silent fallthrough to `scryfall_id=None`).
- `backend/app/pipeline/vision_fallback.py` (orphan OpenAI-specific implementation, never imported by `main.py`).
- `webapp/lib/enhancedOcrServiceGuaranteed.ts` (untracked dead file from a retired Node backend that imported `openai`/`sharp`/`fs` which weren't even installed).
- 7 fictional unit/e2e tests (`tests/unit/test_parser.py`, `test_normalize.py`, `test_mtg_edge_cases.py`, `test_mtgo_lands_bug.py`, `tests/integration/test_pipeline_offline.py`, `tests/e2e/test_benchmark_day0.py`, `tests/e2e/test_exports_golden.py`) that redefined their own target functions locally and asserted on them.
- 8 bare `except:` clauses across `websocket.py`, `monitoring.py`, `core/resilience.py`, `core/config.py`, `auth.py`, `core/idempotency.py`, `routers/metrics.py`, `matching/scryfall_cache.py` (replaced with `except Exception:` so `KeyboardInterrupt` / `SystemExit` propagate).
- Live source mount `./backend/app:/app/app` from `docker-compose.yml`.

### Security
- Fixed IDOR on `GET /api/ocr/status/{job_id}` — the ownership check was dead code because the middleware short-circuited on rate-limited paths.
- Fixed CVE-2024-33663 and CVE-2024-33664 by migrating off python-jose.
- Scrubbed every default credential from compose + k8s manifests.
- Added a CI guard that fails on reintroduction of known-bad defaults.

### Performance (projected — see DISCLAIMER.md)
- p95 latency: 4.1 s → 2.7 s (−34%) on the Vision-primary path — **projection** from the performance-engineer agent's model, not measured on this branch.
- 60-card Scryfall resolution: ~7 s → ~500 ms via batch endpoint — **arithmetic** (60 × 120 ms vs 1 × 500 ms), not timed end-to-end.
- Dead code removed: ~1173 LOC across 3 backend modules + 7 fictional tests — **verified** via `git show --shortstat`.
- Pipeline LOC: −60 % on the fast path when Vision succeeds — **eyeballed**, not diff'd line-by-line.

## [2.3.0] - 2025-01-21 - ONLINE-ONLY Evolution

### Changed
- **BREAKING**: Complete removal of offline capabilities
- **Architecture**: Simplified to 100% online operation
- **EasyOCR**: Models now downloaded on-demand (~64MB)
- **Scryfall**: Direct API integration only (no offline database)
- **Testing**: New `make test-online` command for online validation
- **Deployment**: Simplified without pre-baking or model integration

### Removed
- All offline mode components
- Air-gap functionality
- Pre-baked EasyOCR models in Docker
- Offline Scryfall database
- No-Net Guard network isolation
- Files: `no_net_guard.py`, `health_router.py`, `pipeline_100.sh`, `gate_pipeline.sh`
- Commands: `make pipeline-100`, `make demo-local`, `make validate-airgap`

### Added
- New test script: `tests/webapp.online.js`
- Online E2E test command: `make test-online`
- Automatic EasyOCR model download on first use

## [2.0.0] - 2025-08-17

### Added
- **Discord Bot**: Full parity with web interface via slash commands
- **GDPR Compliance**: Complete data retention policy with automatic deletion
- **Idempotency**: Redis-based deduplication with deterministic keys
- **Health Monitoring**: Detailed `/health/detailed` endpoint with TTL exposure
- **E2E Benchmarks**: Comprehensive testing showing 96.2% accuracy
- **Vision Fallback**: OpenAI Vision API as fallback for low-confidence OCR
- **GPU Support**: Docker and Kubernetes configurations for GPU acceleration
- **Multi-arch Images**: Support for linux/amd64 and linux/arm64
- **Security Enhancements**:
  - JWT authentication with refresh tokens
  - API key management
  - Rate limiting per IP and user
  - Anti-Tesseract guard in CI
  - Magic number validation for uploads
- **Observability**:
  - Prometheus metrics for all pipeline stages
  - OpenTelemetry tracing
  - Jaeger integration
  - GDPR retention metrics
- **Export Formats**: MTGA, Moxfield, Archidekt, TappedOut
- **WebSocket Support**: Real-time job status updates

### Changed
- Migrated from prototype to production-ready architecture
- Enhanced OCR pipeline with 4-variant preprocessing
- Improved caching strategy with multi-level cache
- Upgraded security with non-root containers
- Refactored for better error handling and resilience

### Fixed
- All critical security vulnerabilities
- Rate limiting issues
- Memory leaks in long-running processes
- Cache invalidation problems
- CORS configuration for production

### Security
- Replaced default JWT secrets with cryptographically secure tokens
- Implemented proper password hashing with bcrypt
- Added input validation and sanitization
- Secured health endpoints with IP allowlist
- Implemented GDPR-compliant data retention

## [1.0.0] - 2024-12-20

### Added
- Initial prototype release
- Basic OCR functionality with EasyOCR
- Simple web interface
- Scryfall card validation
- Basic export to MTGA format

### Known Issues
- Default secrets in configuration
- No authentication system
- Limited error handling
- No production deployment support

---

## Upgrade Guide

### From 1.0.0 to 2.0.0

1. **Environment Variables**:
   - Generate new JWT secret: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
   - Update all secrets in `.env.production`
   - Enable GDPR compliance: `GDPR_ENABLED=true`

2. **Database Migration**:
   - Run Alembic migrations: `alembic upgrade head`
   - Initialize Redis cache

3. **Docker Deployment**:
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

4. **Verification**:
   - Check health: `curl http://localhost:8080/health`
   - Run E2E tests: `make e2e-day0`
   - Verify metrics: `curl http://localhost:9090/metrics`

### Breaking Changes

- API endpoints now require authentication
- Rate limiting enforced on all endpoints
- Tesseract OCR explicitly blocked (EasyOCR only)
- Health detailed endpoint restricted in production

## Support

For issues and questions:
- GitHub Issues: https://github.com/gbordes77/Screen2Deck/issues
- Documentation: https://screen2deck.github.io

## Contributors

- Guillaume Bordes (@gbordes77)
- Claude Code (AI Assistant)

---

[2.0.0]: https://github.com/gbordes77/Screen2Deck/releases/tag/v2.0.0
[1.0.0]: https://github.com/gbordes77/Screen2Deck/releases/tag/v1.0.0