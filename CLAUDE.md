# CLAUDE.md - Screen2Deck AI Assistant Guide

This file provides guidance to Claude Code when working with the Screen2Deck repository.

## Project Status: Production Ready (v2.4.0)

**Latest Update**: 2026-04-17 — OCR-first policy flip (AI becomes an opt-in backup)

Highlights of the 2026-04-17 session:

- **Default OCR path reverted to EasyOCR + OpenCV** — MTG community feedback flagged the Vision-primary default as a trust issue. `VISION_PRIMARY` now defaults to **false** in `backend/app/config.py`, `backend/app/core/config.py`, `docker-compose.yml`, and `backend/.env.docker`. A fresh `docker compose up` no longer calls Gemini or Claude; the deterministic preprocess → EasyOCR best-of → regex parser → Scryfall batch pipeline is the canonical route. Operators who prefer the LLM fast path can still flip `VISION_PRIMARY=true`.
- **EasyOCR parameters tuned for game screenshots** — `pipeline/ocr.py::run_easyocr` now passes `contrast_ths=0.1`, `adjust_contrast=0.5`, `text_threshold=0.6`, `low_text=0.3`, `link_threshold=0.4`, `mag_ratio=1.5`, `canvas_size=2560`. Sourced from the EasyOCR docs via context7 (`/jaidedai/easyocr`) — the contrast adjustments in particular lift dark MTGO screenshots that CLAHE alone under-processed.
- **Vision path is now explicitly a backup** — `ENABLE_VISION_FALLBACK=true` stays the default so low-confidence scans can still escalate, but the module docstring in `pipeline/vision_providers.py` and the env-var comments in both config modules now describe the LLM chain as a backup, not the main route.
- **Docs realigned** — README hero copy, architecture diagram, and env-var table rewritten to describe an OCR-primary system with AI as opt-in backup.

**Previous session (2026-04-16)**: Post-merge stabilization wave (6-agent audit + fixes)

Highlights of the 2026-04-16 session (on top of the 2026-04-14 consolidation):

- **Real IDOR fix** — the v2.4.0 ownership check on `/api/ocr/status/{job_id}` was still dead code: `main.py` captured `user_id = token_data.job_id` while the login endpoint mints tokens with the user id under the `user_id` claim. Added `user_id` to `TokenData`, populated it in `verify_token` and `_parse_bearer`, swapped `main.py::upload_image` to `token_data.user_id`. Ownership check now actually fires.
- **`/api/auth/api-key` no longer world-writable** — previously the endpoint accepted a POST from anyone on the internet and returned a working API key. Now requires `Depends(get_current_token)`.
- **CSP hardened in production** — `SecurityHeadersMiddleware` now gates `'unsafe-inline'` / `'unsafe-eval'` behind `APP_ENV != "production"` so dev-mode Next.js keeps working but prod does not ship with script injection flags.
- **CI secrets-scan unblocked** — `Makefile::ci-health` no longer bakes `postgres:postgres` into `backend/.env.docker`, `backend/.env.docker.example` lost the literal default string, and the guard in `security-checks.yml` now excludes `*.html` + `.venv*` so it stops false-positiving on its own documentation.
- **Dead modules purged** — deleted `backend/app/routers/metrics.py` (imported but never mounted, defined stale `screen2deck_*` collectors as a second registry), `backend/app/telemetry_full.py` (never imported), and dropped `celery==5.6.3` / `asyncpg==0.31.0` / `locust==2.43.4` from `backend/requirements.txt` (orphan deps after the 2026-04-14 cleanup).
- **`/health` version stamp** — `routers/health.py` now reports `2.4.0` instead of `2.0.0`.
- **Makefile test targets** — `make test` now = `make unit` (Python tests/unit/ only). `make integration` exits with a pointer to `make smoke` / `make e2e-smoke`. `make e2e` aliases to `make e2e-ui` (Playwright). `ci.yml::test-backend` no longer discovers the orphan `backend/tests/conftest.py` (which was importing the legacy config module).
- **Docs realigned with reality** — README and CLAUDE.md no longer advertise Gemini 3.1 Flash-Lite (the preview model was saturated and the code already fell back to `gemini-2.5-flash`; this session made the docs match). Architecture diagrams, pipeline steps, env blocks, and metric claims now point at the v2.4.0 Vision-primary default. `docs/how-it-works.html` (stale hand-maintained HTML) was deleted.

**Previous session (2026-04-14)**: Re-architecture consolidation + Vision migration (PR #2)

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

Two code paths coexist in `main.py::process_ocr`. The **default is the
EasyOCR + OpenCV primary path**; the Vision LLM path is an opt-in
alternative + a low-confidence backup.

```
EasyOCR-primary (default, VISION_PRIMARY=false):
1. IMAGE UPLOAD → Validation and storage
2. PREPROCESSING → 4 variants (Original, CLAHE, Denoised+Sharpened,
   Adaptive threshold); optional 4× super-res below SUPERRES_MIN_WIDTH
3. EASYOCR best-of → contrast-lifted, mag_ratio=1.5, canvas_size=2560,
   early-stop at OCR_EARLY_STOP_CONF (0.85)
4. CONFIDENCE CHECK → If mean conf < OCR_MIN_CONF (0.62)
   OR qty-line count < OCR_MIN_LINES (10)
   AND ENABLE_VISION_FALLBACK=true AND a provider has an API key:
     retry with Vision chain (Gemini 2.5 Flash → Claude Haiku 4.5).
   Otherwise EasyOCR's best-effort result is used as-is.
5. PARSE_DECK_SECTIONS → Regex parser over OCR spans
6. SCRYFALL BATCH VALIDATION → /cards/collection (75 IDs per request)
7. MTGO 60+15 REDISTRIBUTION (apply_mtgo_land_fix)
8. EXPORT → MTGA, Moxfield, Archidekt, TappedOut

Vision-primary (opt-in, VISION_PRIMARY=true):
1. IMAGE UPLOAD → Validation and storage
2. VISION LLM → Gemini structured JSON → Claude tool-use fallback,
   typed {main, side} output, skips preprocess + EasyOCR + regex
3. On Vision failure → EasyOCR-primary path above as full fallback
4. SCRYFALL BATCH VALIDATION → Same as above
5. EXPORT → Same as above
```

**Important**: This project uses EasyOCR (never Tesseract) as the primary OCR engine.

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
# Default in v2.4.0 (post 2026-04-17) is VISION_PRIMARY=false — EasyOCR
# + OpenCV is the primary path. All knobs below are live on that path.
ENABLE_VISION_FALLBACK=true      # Keep the Vision LLM chain wired as a low-conf backup
VISION_PRIMARY=false             # Leave false to keep OCR as the primary path
ENABLE_SUPERRES=true             # 4× upscaling for small images
OCR_MIN_CONF=0.62                # Trigger Vision backup below this
OCR_EARLY_STOP_CONF=0.85         # EasyOCR early-stop threshold
OCR_MIN_SPAN_CONF=0.3            # Min confidence per text span
SUPERRES_MIN_WIDTH=1200          # Trigger super-res below this width

# Vision providers (v2.4.0+)
VISION_PROVIDER=gemini,claude    # Comma-separated chain, first available wins
GEMINI_API_KEY=                  # Free tier at https://aistudio.google.com/app/apikey
GEMINI_MODEL=gemini-2.5-flash    # Stable GA — preview Flash-Lite was unreliable
ANTHROPIC_API_KEY=               # Optional — API access is separate from Claude Pro/Max
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
6. **Rate limiting errors**: per-endpoint IP limits enforced by `core/auth_middleware.py` (upload 10/min burst 3, status 60/min burst 10, export 20/min burst 5). Add delays in benchmark scripts.
7. **Vision API not triggering**: on the default OCR-primary path it only runs when mean confidence drops below `OCR_MIN_CONF` (0.62) or fewer than `OCR_MIN_LINES` (10) qty-lines are found — a clean Arena screenshot should stay entirely on EasyOCR. If you want to force the LLM path for testing, set `VISION_PRIMARY=true`.
8. **No Gemini/Anthropic key configured**: the Vision chain is a no-op and EasyOCR's best-effort result is returned as-is. This is the intended "OCR-only" deployment mode.

## Testing

Post-v2.4.0 test-honesty pass, the only real Python unit tests live in
`tests/unit/`:
- `test_business_rules.py` — MTGO 60+15 redistribution (5 cases)
- `test_exporters.py` — Archidekt/MTGA/Moxfield/TappedOut CSV escaping + split cards (6 cases)
- `test_no_tesseract.py` — anti-Tesseract guard (4 cases)

Playwright e2e lives in `tests/web-e2e/` and runs via `make e2e-ui` or
`make e2e-smoke`. Golden exports are covered by `make golden` (via
`tools/golden_check.py`) and `make exports-goldens` (HTTP contract test
against a running backend).

Run `make test` for the Python unit suite. The old `make integration`
and `make e2e` Python targets point at directories that were deleted in
v2.4.0 and now emit a pointer to their replacements.

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

4. **DONE.md** (append-only) + **PLAN.md** (live backlog) - Complement HANDOFF.md
   - DONE.md: every completed item linked to a commit SHA (never edited in place)
   - PLAN.md: unfinished work with severity tags (🔴 blocks merge, 🟠 ships with merge, 🟡 tech debt, 🔵 decision needed)
   - SESSION_NOTES.md: free-form narrative for the current session

### Session End Checklist
- [ ] Update HANDOFF.md with today's work
- [ ] Add technical notes to CLAUDE.md
- [ ] Update README.md if public changes
- [ ] Commit with clear message
- [ ] Note any unresolved issues