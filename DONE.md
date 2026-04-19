# DONE — append-only log

Append-only history of completed work. Never edit or delete past entries.
New work goes at the **top** (most recent first), linked to a commit SHA.

Status legend: ✅ verified end-to-end · 🟢 committed, not yet verified · 📝 doc-only

---

## 2026-04-16 — Post-merge stabilization (6-agent audit + atomic fixes)

### Security (Tier 0)
- 🟢 **Real IDOR fix** — `TokenData` gains a `user_id` field, populated in `auth.verify_token` and `core/auth_middleware._parse_bearer`; `main.py::upload_image` switched from `token_data.job_id` (always None) to `token_data.user_id`. The ownership check on `/api/ocr/status/{job_id}` was dead code since v2.4.0 because the login endpoint mints tokens with `user_id` as the claim name.
- 🟢 **`/api/auth/api-key` now requires auth** — previously a world-writable key-mint endpoint. Added `Depends(get_current_token)`. `POST /api/auth/logout` also requires auth now (documented as stateless no-op).
- 🟢 **CSP prod hardening** — `SecurityHeadersMiddleware` gates `'unsafe-inline'` / `'unsafe-eval'` behind `APP_ENV != "production"`. Added `frame-ancestors 'none'`, `base-uri 'self'`, `form-action 'self'`.

### CI unblock (Tier 0)
- 🟢 `Makefile::ci-health` no longer writes `postgres:postgres` into `backend/.env.docker`. `backend/.env.docker.example` cleaned of all literal defaults.
- 🟢 `security-checks.yml::secrets-scan` guard excludes `*.html` + `.venv*` to stop false-positiving on its own documentation (the stale `docs/how-it-works.html` embedded the guard pattern list, so the guard was matching itself).
- 🟢 `docs/how-it-works.html` deleted (stale hand-maintained HTML, redundant with `docs/index.md` + mkdocs).
- 🟢 `.github/workflows/ci.yml::test-backend` — pytest scope narrowed from `tests/ backend/tests/` to `tests/unit`. The `backend/tests/` path only picked up the orphan conftest that imports the legacy config module.

### Cleanup (Tier 1)
- 🟢 **Dead router deleted** — `backend/app/routers/metrics.py` (imported via `routers/__init__.py` but never mounted in `main.py`; real `/metrics` is a sub-app from `core/metrics_minimal.create_metrics_app`).
- 🟢 **Unused telemetry variant deleted** — `backend/app/telemetry_full.py` (397 LOC, zero importers).
- 🟢 **Dead dependencies dropped** — `celery==5.6.3` (Celery tasks.py was deleted in PR #2), `asyncpg==0.31.0` (forbidden by CLAUDE.md, never imported), `locust==2.43.4` (belongs in dev extras). Also dropped `opentelemetry-instrumentation-celery`.
- 🟢 **Version stamp** — `routers/health.py` basic + detailed endpoints now report `2.4.0` (was `2.0.0`).
- 🟢 **Makefile test targets realigned** — `make test` = `make unit` (only Python tests that exist). `make integration` emits a pointer to `make smoke` / `make e2e-smoke` / `make exports-goldens`. `make e2e` aliases to `make e2e-ui`.

### Docs realigned with reality (Tier 2)
- 📝 `README.md` — every "Gemini 3.1 Flash-Lite" → "Gemini 2.5 Flash"; perf metrics reframed as projected (see DISCLAIMER.md); `OPENAI_API_KEY` env block replaced with `GEMINI_API_KEY`/`ANTHROPIC_API_KEY`/`VISION_PRIMARY`; duplicate contradictory ASCII architecture diagram deleted; broken `pytest tests/integration` + `pytest tests/e2e` lines removed with pointer to Playwright.
- 📝 `CLAUDE.md` — new 2026-04-16 "Latest Update" block; OCR pipeline diagram rewritten to show both code paths; `GEMINI_MODEL=gemini-2.5-flash`; stale `30 req/min` rate-limit note fixed; SESSION_NOTES optional entry replaced with DONE/PLAN/SESSION_NOTES split.
- 📝 `docs/ARCHITECTURE.md` — `v2.3.0 → v2.4.0`, Celery + OpenAI dropped from mermaid, Gemini + Claude added.
- 📝 `docs/index.md` — "100% Offline Capable" lie replaced with online-only GDPR pointer; perf table reframed as targets; mermaid rewritten with Vision-primary branching.
- 📝 `docs/CONFIGURATION.md` — k8s Secret example no longer ships literal `your-super-secret-jwt-key` / `sk-your-openai-api-key`.
- 📝 `docs/DEPLOYMENT.md` — `hash_password('changeme')` rewritten to read from `ADMIN_PASSWORD` env.
- 📝 `docs/SECURITY.md` — rate-limit table matches the actual values in `core/auth_middleware.py`.
- 📝 `docs/VISION_FALLBACK_POLICY.md` — top banner explains the doc covers the legacy path.

### Tracking
- 🟢 `.gitignore` updated to cover `backend/.venv-upgrade/` (1.1 GB), `validation_set/imported_from_old_project/` (24 MB), `webapp/tsconfig.tsbuildinfo`, `*.tsbuildinfo`, `backend/backend.log`, `webapp/frontend.log`.
- 🟢 `backend/.venv-upgrade/` (1.1 GB intermediate venv from the 2026-04-15 dep sweep) + `webapp/tsconfig.tsbuildinfo` deleted on disk. `validation_set/imported_from_old_project/` kept on disk (gitignored) pending user decision on whether to promote it into the canonical corpus.

Audit trail: six parallel sub-agents (`context-manager`, `documentation-expert`, `Security-Auditor`, `qa-expert`, `performance-engineer`) ran read-only audits. Findings landed in `/tmp/context-manager-briefing-2026-04-16.md` (20 drift items) and the orchestrator applied the atomic fixes above on a single commit.

---

## 2026-04-15 — Methodology audit + stop-the-bleeding

### Wave 1: stop the bleeding (`81b4ab6`)
- ✅ **Settings defaults aligned** — both `backend/app/config.py` and `backend/app/core/config.py` now default to `gemini-2.5-flash` / `VISION_PRIMARY=True` / `ENABLE_VISION_FALLBACK=True`. Warning comments added pointing at the known duplication (full consolidation deferred to ADR 0005).
- ✅ **Version stamp fix** — `backend/app/main.py:137,559` `version="2.0.0"` → `"2.4.0"`. `curl /health` and `curl /` now agree with the docs.
- 📝 **README architecture diagram** — `README.md:90` OpenAI Vision → Gemini 2.5 / Claude Haiku.
- 🟢 **Dead file duplicates removed** — `CLAUDE copie.md` (macOS Finder dup, 252 lines) + `security-audit-report.md` (lowercase casing dup of `SECURITY_AUDIT_REPORT.md`) both `git rm`ed.
- 📝 **release.yml hallucinated metrics** — hard-coded "96.2% accuracy / 2.45s P95" replaced with pointers to `reports/day0/` and `DISCLAIMER.md`. Workflow itself remains dormant.

### Wave 2 so far: cleanup
- 🟢 **21 stale root docs + stale doc subtrees removed** — Aug 2025 tombstones deleted: `CHANGELOG_v2.0.2.md`, `E2E_*_ASSESSMENT.md` ×3, `GATE_FINAL_SUMMARY.md`, `IMPROVEMENTS_IMPLEMENTED.md`, `MIGRATION_v2.3.0.md`, `PERFORMANCE_ANALYSIS.md`, `PERFORMANCE_LOAD_REPORT.md`, `PRODUCTION_READY.md`, `PROOF_SUMMARY.md`, `REAL_E2E_TEST_ASSESSMENT.md`, `RELEASE_NOTES_v2.3.0.md`, `SANITY_CHECKLIST.md`, `SECURITY_AUDIT_REPORT.md`, `TEAM_HANDOVER.md`, `TESTING.md`, `TEST_PLAN_PLAYWRIGHT.md`, `MTG_Deck_Scanner_Docs_v2/` (full 19-file subtree), `docs/site/` (empty mkdocs build artifact).

### Today's earlier work: dependency upgrade sweep + Vision-primary fix

- ✅ **`a54d6aa` chore(security)** — Next.js 14.2.5 → 14.2.35 (CVE-2025-55184 + CVE-2025-67779 DoS fixes), Node 20 → 22 (Node 20 EOL 2026-04-30), Redis 7-alpine → 7.4-alpine across all compose files and CI workflows.
- ✅ **`655bbab` chore(deps)** — 30+ backend package bumps: fastapi 0.115 → 0.135, pydantic 2.9 → 2.13, sqlalchemy 2.0.34 → 2.0.49, PyJWT 2.8 → 2.12, cryptography 42 → 46, pytest 7 → 9, pytest-asyncio 0.21 → 1.3, redis-py 5 → 7, celery 5.3 → 5.6, EasyOCR 1.7.1 → 1.7.2, opencv 4.10 → 4.13, numpy 2.1 → 2.4, Pillow 10 → 12, OpenTelemetry 1.21/0.42b0 → 1.41/0.62b0, locust 2.17 → 2.43, psutil 5.9 → 7.2. Also drops the deprecated `event_loop` session fixture from `backend/tests/conftest.py` (forbidden in pytest-asyncio ≥0.24).
- ✅ **`0d2846a` feat(vision)** — google-genai 0.8 → 1.73.1 + anthropic 0.39 → 0.95. Migrated `vision_providers.py` `response_schema=` → `response_json_schema=` (the canonical field for raw JSON Schema dicts in google-genai 1.x). Default Gemini model swapped from the saturated `gemini-3.1-flash-lite-preview` to the stable `gemini-2.5-flash`.
- ✅ **`009e02b` fix(deploy)** — discovered via smoke test: the v2.4.0 Vision-primary fast path was committed in `main.py` but never wired in `docker-compose.yml`, so every deployment since v2.4.0 was silently running EasyOCR-only. Fixed by forwarding `ENABLE_VISION_FALLBACK` / `VISION_PRIMARY` / `VISION_PROVIDER` / `GEMINI_MODEL` / `ANTHROPIC_MODEL` / `REDIS_URL` in the compose `environment:` block with safe defaults.

### Methodology audit — 6 agents ran
- ✅ **context-manager** bootstrap scan → `sub-agents/context/context-manager.json` (51 KB, 18 top-level keys)
- ✅ **agent-organizer** meta-assessment → identified "audit-driven big-bang refactor branch with no release discipline"
- ✅ **qa-expert** → flagged zero coverage on `run_vision_chain_structured` + IDOR fix, dead `s5-vision-fallback.spec.ts`, `MIN_MAIN_CARDS=20` too lax
- ✅ **documentation-expert** → 21 stale root docs + 2 duplicates + 2-Settings drift + README OpenAI drift
- ✅ **devops-engineer** → 3 version-drift inconsistencies across 9 workflows, k8s is aspirational, no image digest pinning, reusable `compose-up-core` workflow recommended
- ✅ **project-planner** → NEXT_STEPS.md is retrospective not prospective (0/4 post-plan commits mapped), no decision log, recommended PLAN.md + DONE.md split

### End-to-end smoke test

- ✅ **`tests/smoke_test.sh --no-boot`** green end-to-end against the upgraded backend image: `main=60 (20 distinct) / side=15 (9 distinct)`, Scryfall resolution 20/20 (100%), MTGA export 32 lines. First 5 cards: Into the Flood Maw, Opt, Sleight of Hand, Stormchaser's Talent, Torch the Tower. Method = `vision_gemini_structured` (Vision-primary path confirmed exercised).

---

## 2026-04-14 — v2.4.0 consolidation (previous session)

See `HANDOFF.md` and `SESSION_NOTES.md` for the full 14-item wave log. Summary: deleted `main_original.py` / `main_refactored.py` / `tasks.py` / `services/ocr_service.py` / `matching/scryfall_cache.py` (correctness bug: cache perpetually cold) / `pipeline/vision_fallback.py` / 7 fictional test files; migrated OpenAI → Gemini + Claude; restored `apply_mtgo_land_fix` from no-op stub to real redistribution; added Scryfall `/cards/collection` batch endpoint; fixed IDOR on `/api/ocr/status/{job_id}`; python-jose → PyJWT (CVE-2024-33663 + CVE-2024-33664); default-credential scrubbing in compose + k8s; frontend strict TypeScript + a11y + error boundaries.

Commits: `b134dd1` → `1da59e4` (32 commits).
