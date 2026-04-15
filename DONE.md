# DONE — append-only log

Append-only history of completed work. Never edit or delete past entries.
New work goes at the **top** (most recent first), linked to a commit SHA.

Status legend: ✅ verified end-to-end · 🟢 committed, not yet verified · 📝 doc-only

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
