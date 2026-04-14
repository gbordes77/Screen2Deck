# CLAUDE.md - Screen2Deck AI Assistant Guide

This file provides guidance to Claude Code when working with the Screen2Deck repository.

## Project Status: Production Ready (v2.4.0)

**Latest Update**: 2026-04-14 — Re-architecture consolidation + Vision migration (PR #2)

Landed on `refactor/consolidation-2026-04-14` in 13 commits:

1. **Backend consolidation** — deleted `main_original.py`, `main_refactored.py`, `migrate_to_production.py`, `tasks.py` (Celery dead path), `services/ocr_service.py` (orphan), `matching/scryfall_cache.py` (correctness bug: cache perpetually cold), `webapp/lib/enhancedOcrServiceGuaranteed.ts`, and `pipeline/vision_fallback.py`. Canonical backend entry is now unambiguously `main.py`.
2. **Restored MTGO 60+15 feature** — `business_rules.apply_mtgo_land_fix` went from a no-op stub to real redistribution logic and is now wired into the canonical pipeline. The v2.3.0 feature was shipped but never called on the real code path.
3. **Fixed circuit breaker** — `core/circuit_breaker.py` had broken import paths that made the whole module unimportable.
4. **Vision migration: OpenAI → Gemini 3.1 Flash-Lite + Claude Haiku 4.5** — dropped `openai==1.3.0`, added `google-genai>=0.8.0` + `anthropic>=0.39.0`. New `pipeline/vision_providers.py` with `VisionProvider` ABC, `GeminiVisionProvider`, `ClaudeVisionProvider`, chain logic, and structured-output methods (`extract_deck_structured`) using Gemini `response_schema` and Claude tool-use.
5. **VISION_PRIMARY fast path** — new feature flag routes Vision LLM FIRST with typed JSON output, skipping preprocessing + EasyOCR + regex parser. EasyOCR falls back when the model call fails. Modelled at p95 4.1 s → 2.7 s, accuracy +3–5 pts, cost ~$0.39/day at 1000 req/day with free-tier absorption.
6. **Scryfall batch endpoint** — new `SCRYFALL.batch_resolve()` uses `/cards/collection` (75 IDs per request) instead of N serial `/cards/named?fuzzy=` calls. Added mandatory User-Agent header (required by Scryfall policy since 2024). `normalize_deck` rewritten through `asyncio.to_thread` so sync sqlite / requests / sleep no longer block the event loop. Rate limit bumped 120 → 100 ms to match the official 10 req/s guideline.
7. **Scryfall bulk hydrate at startup** — `main.py` lifespan now calls `SCRYFALL.hydrate_from_bulk` via `asyncio.to_thread` when the bulk file is on disk. `all_names()` is memoized process-level behind a `threading.Lock`.
8. **Security: IDOR fix on /api/ocr/status** — `AuthMiddleware` had two short-circuit bypasses (`RATE_LIMITED_PUBLIC` + `/api/export/*`) that made `request.state.token_data` always None, so the ownership check in `get_job_status` was dead code. Rewrote the middleware as optional-auth (populates state, never 401s, rate-limits). Endpoints use `Depends(get_optional_token)` and enforce ownership unconditionally when `job.user_id` is set.
9. **Security: python-jose → PyJWT** — fixes CVE-2024-33663 (algorithm confusion) and CVE-2024-33664 (JWT decompression bomb). All callers (`auth.py`, `auth_middleware.py`, `auth_router.py`, `api/websocket.py`) now `import jwt; from jwt import InvalidTokenError`. Every `jwt.decode(...)` call adds `options={"require": ["exp"]}` to reject unsigned or no-exp tokens.
10. **Security: default-credential scrubbing** — every `postgres:postgres`, `changeme`, `your-super-secret`, `dev-secret-key-change-in-production` replaced by `${VAR:?}` substitution in `docker-compose.yml` / `docker-compose.local.yml` or `__REPLACE_ME__` markers in `k8s/secrets.yaml` / `k8s/postgres-deployment.yaml`. `backend/.env.docker` now carries only non-sensitive knobs. CI guard added to `security-checks.yml` that fails on any reintroduction.
11. **Frontend strict TypeScript** — `tsconfig strict: true + noUncheckedIndexedAccess + noImplicitOverride`. `lib/api.ts` rewritten with typed domain models (`NormalizedCard`, `NormalizedDeck`, discriminated `JobStatus` union, `ApiError` class). Every fetch now routes through a single `request<T>` helper. All public functions accept an optional `AbortSignal`.
12. **Frontend a11y + error boundaries** — added `app/error.tsx`, `app/loading.tsx`, `app/result/[jobId]/error.tsx`, `app/result/[jobId]/loading.tsx`. `app/result/[jobId]/page.tsx` uses `AbortController` + cancelled flag on polling so `setState` never fires on an unmounted tree. `alert()`-based "copied" notice replaced with an `aria-live="polite"` region. File input has a real `<label>`, spinner has `aria-hidden`, all buttons have `focus-visible` rings. `<html lang>` fixed to match the UI language.
13. **Test honesty** — deleted 7 fictional test files (`tests/unit/test_parser.py`, `test_normalize.py`, `test_mtg_edge_cases.py`, `test_mtgo_lands_bug.py`, `tests/integration/test_pipeline_offline.py`, `tests/e2e/test_benchmark_day0.py`, `tests/e2e/test_exports_golden.py`) that defined their own target functions locally and asserted on them — they tested their own fiction. Replaced with `tests/unit/test_business_rules.py` (5 cases exercising real MTGO redistribution) and `tests/unit/test_exporters.py` (6 cases exercising CSV escaping on real `Knight, Errant` / `Fire // Ice` cards).
14. **CI hardening** — removed every `|| true` in `proof-tests.yml` that silenced pytest/bench/golden/parity failures. Fixed `ci.yml` pytest path. Dropped the `|| true` on the webapp type-check step.

**Previous Updates**:
- 2025-08-23: OCR improvements (Vision fallback thresholds, super-resolution, MTGO segmentation, benchmark suite, website format parsing)
- 2025-08-19: Online-only operation with Scryfall API integration
- EasyOCR models downloaded on-demand (~64MB on first run)
- No offline capabilities - requires internet connection
- Core services: Redis, PostgreSQL, Backend (FastAPI), Frontend (Next.js)

## Current Technical Notes

### Architecture (v2.4.0)
- **Canonical entry point**: `backend/app/main.py` (uvicorn target in `Dockerfile`). No more `main_original.py` / `main_refactored.py` variants.
- **OCR pipeline has two code paths**:
  - **Vision-primary fast path** (`VISION_PRIMARY=true` + provider available): `run_vision_chain_structured` calls Gemini then Claude with a JSON schema constraint, returns typed `{main, side}`. Skips preprocessing + EasyOCR + regex parser entirely.
  - **EasyOCR legacy path** (default): `preprocess_variants` → `run_easyocr_best_of` → Vision fallback on low confidence → `parse_deck_sections`. Unchanged semantics for operators who haven't flipped the flag.
- **Scryfall resolution** goes through `SCRYFALL.batch_resolve(names)` via `asyncio.to_thread`. Fallbacks to `SCRYFALL.resolve(name)` per card for names the batch couldn't match.
- **Auth flow**: optional at the middleware level, endpoints decide. `get_optional_token` reads `request.state.token_data`. Ownership check on `/api/ocr/status/{job_id}` requires matching `user_id` when the job was created authenticated.
- **Vision providers**: new module `backend/app/pipeline/vision_providers.py` with `VisionProvider` ABC, `GeminiVisionProvider`, `ClaudeVisionProvider`. Each has `extract_deck` (plain text) and `extract_deck_structured` (JSON schema / tool-use).

### Documentation State
- ✅ Cleaned and professional tone (no more defensive language)
- ✅ Session tracking system implemented globally
- ✅ All inconsistencies fixed (accuracy, version, links, etc.)
- ✅ Load testing evidence documented
- ✅ Privacy/external APIs clearly documented
- ⚠️ PROOF_SUMMARY.md might be redundant (consider removal)

### Technical Discoveries (2026-04-14)
- Scryfall requires `User-Agent` + `Accept` headers since 2024 — `python-requests/x.y` is throttled harder and may be blocked.
- `/cards/collection` batch endpoint (75 IDs/req) collapses 60-card decks from ~7 s to ~500 ms.
- Gemini 3.1 Flash-Lite `response_schema` + Claude tool-use both return typed deck JSON directly — kills the regex parser on the happy path.
- `backend/app/matching/scryfall_cache.py` had a perpetual cold-cache bug (`save_card` was never reachable), so the whole async cache layer fell through to `scryfall_id=None`. Deleted in PR #5.
- `tasks.py` (Celery worker) had a double-escaped regex (`r"^\\s*(\\d+|[1-9]\\dx)\\s+\\S+"`) that matched nothing. Deleted in PR #5.
- python-jose 3.3.0 is affected by CVE-2024-33663 and CVE-2024-33664 — migrated every consumer to PyJWT.

## OCR Processing Pipeline

The OCR flow is critical to the application's functionality:

```
1. IMAGE UPLOAD → Validation and storage
2. PREPROCESSING → 4 variants (Original, Denoised, Binarized, Sharpened)
3. EASYOCR → Primary OCR engine (multi-pass with 85% confidence threshold)
4. CONFIDENCE CHECK → If <62%, optional Vision API fallback
5. SCRYFALL VALIDATION → Mandatory API verification for all cards
6. EXPORT → Multiple formats (MTGA, Moxfield, Archidekt, TappedOut)
```

**Important**: This project uses EasyOCR exclusively. Tesseract is not supported.

## Project Structure

```
/
├── backend/           # FastAPI backend
│   ├── app/
│   │   ├── main.py   # API endpoints
│   │   ├── pipeline/ # OCR processing
│   │   ├── matching/ # Card resolution
│   │   └── exporters/# Export formats
├── webapp/           # Next.js frontend
│   ├── app/         # App router pages
│   └── lib/         # Utilities
├── tests/           # Test suites
├── tools/           # Benchmarking tools
└── docker-compose.yml
```

## Key Configuration

### Database
- Use `psycopg[binary]` (never asyncpg)
- PostgreSQL URL: `postgresql+psycopg://`
- Docker PostgreSQL: Port 5433 externally (5432 internally)

### Environment Variables
```env
# Core Settings (Never change)
ALWAYS_VERIFY_SCRYFALL=true      # Never disable
FEATURE_TELEMETRY=false          # Disable in dev

# OCR Configuration
ENABLE_VISION_FALLBACK=true      # Turn on Vision LLM path at all
VISION_PRIMARY=true              # Route Vision LLM FIRST, EasyOCR fallback (v2.4.0+)
ENABLE_SUPERRES=true             # 4× upscaling for small images (legacy path only)
OCR_MIN_CONF=0.62                # Trigger Vision fallback below this (legacy path only)
OCR_EARLY_STOP_CONF=0.85         # EasyOCR early-stop threshold (legacy path only)
OCR_MIN_SPAN_CONF=0.3            # Min confidence per text span
SUPERRES_MIN_WIDTH=1200          # Trigger super-res below this width

# Vision providers (v2.4.0+)
VISION_PROVIDER=gemini,claude    # Comma-separated chain, first available wins
GEMINI_API_KEY=...               # Free tier at https://aistudio.google.com/app/apikey
GEMINI_MODEL=gemini-3.1-flash-lite-preview
ANTHROPIC_API_KEY=               # Optional — Claude Pro/Max does NOT include API access
ANTHROPIC_MODEL=claude-haiku-4-5

# Scryfall
SCRYFALL_API_RATE_LIMIT_MS=100   # Official guideline is 10 req/s
```

## Development Commands

```bash
# Quick start
make up              # Start all services
make test-online     # Run E2E tests
make health         # Check health

# Testing
make test           # Unit + integration tests
make bench-day0     # Performance benchmarks
make golden         # Validate export formats
make parity         # Check Web/Discord parity

# Development
make logs           # View logs
make shell-backend  # Backend shell
make down          # Stop services
```

## API Endpoints

- `POST /api/ocr/upload` - Upload image for OCR
- `GET /api/ocr/status/:jobId` - Check processing status
- `POST /api/export/:format` - Export to specific format
- `GET /health` - Health check

## Performance Targets

- Accuracy: ≥85% (fuzzy match)
- P95 Latency: ≤5s
- Cache Hit Rate: ≥50%
- Memory Usage: <500MB per instance

## Common Issues & Solutions

1. **ModuleNotFoundError 'opentelemetry'**: Set `FEATURE_TELEMETRY=false`
2. **Port 5432 already allocated**: Use port 5433 for Docker PostgreSQL
3. **ARM64/M1/M2 Docker build fails**: Remove x86-specific packages from Dockerfile
4. **Performance on CPU**: ~9s average (GPU required for <3s performance)
5. **First run slow**: EasyOCR downloads models (~64MB) on first use
6. **Rate limiting errors**: 30 req/min limit, add delays in benchmark scripts
7. **Vision API not triggering**: Check OCR_MIN_CONF threshold (default 0.62)

## Testing

The project includes comprehensive testing:
- Unit tests with MTG edge cases (DFC, Split, Adventure cards)
- Integration tests for API endpoints
- E2E tests with Playwright (14 test suites)
- Golden tests for export format validation
- Parity tests for Web/Discord consistency

Run `make test` for the complete test suite.

## Code Style

- Backend: Python with type hints
- Frontend: TypeScript with React/Next.js
- All card names validated through Scryfall API
- Follow existing patterns in codebase

## 📝 IMPORTANT: Session Tracking Requirements

### Files to Update at End of Each Session

1. **HANDOFF.md** - Primary session summary
   - What was done today
   - Current state (working/broken)
   - Blockers and issues
   - Next steps for next team

2. **CLAUDE.md** - Technical notes for AI
   - Latest changes with date
   - Current issues/blockers
   - Critical warnings discovered
   - Keep last 3-5 updates

3. **README.md** - Public documentation
   - Update version if major change
   - Add new features to feature list
   - Update performance metrics if improved
   - Keep clean and professional

4. **SESSION_NOTES.md** (Optional) - Detailed session history
   - Create if you want session-by-session history
   - More detailed than HANDOFF.md
   - Include commands run, errors encountered

### Session End Checklist
- [ ] Update HANDOFF.md with today's work
- [ ] Add technical notes to CLAUDE.md
- [ ] Update README.md if public changes
- [ ] Commit with clear message
- [ ] Note any unresolved issues