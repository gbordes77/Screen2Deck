# PLAN — live, checkbox-driven

Live backlog of **unfinished** work. When an item is done, move its line
to `DONE.md` with the commit SHA — **never** uncheck or delete in place.

Severity legend: 🔴 blocks merge · 🟠 ships with merge · 🟡 tech debt · 🔵 decision needed

---

## 🔴 Before merging PR #2 to `main`

- [ ] **CI triage** — PR #2 has ~15 red jobs (`core`, `e2e`, `e2e-mobile`, `e2e-tests (chromium/firefox/webkit)`, `verify-exports`, `security-tests`, `accessibility-tests`, `Lint Code`, `Generate Reproducible Proofs`, `performance-tests`, `bench`). Smoke passes locally. Root cause likely single: missing `POSTGRES_PASSWORD` / `JWT_SECRET_KEY` / `GEMINI_API_KEY` wiring in CI runners since the `${VAR:?}` hardening. Fix: one reusable workflow `compose-up-core.yml` that every downstream `uses:`. **Owner**: TBD. **Blocks**: merge PR #2.
- [ ] **Push current branch to origin** (6 unpushed commits: `a54d6aa`, `655bbab`, `0d2846a`, `009e02b`, `81b4ab6`, + Wave 2/3 when committed). Gated on explicit user OK.

## 🟠 Ship with merge (complete in this session if time allows)

- [ ] **Add 2 unit tests** — `tests/unit/test_vision_providers.py` (mock `google.genai` + `anthropic`, exercise `run_vision_chain_structured` fallthrough Gemini → Claude on exception) and `tests/unit/test_auth_ownership.py` (FastAPI `TestClient`, two JWTs, assert user B gets 403 on user A's job). Identified by qa-expert as "the single biggest regression hole in PR #2".
- [ ] **Delete dead `tests/web-e2e/suites/s5-vision-fallback.spec.ts`** — permanently skipped since OpenAI removal, asserts guarded by `if (await x.count() > 0)` so cannot fail. Either rewrite against the Gemini mock or delete.
- [ ] **Tighten `tests/smoke_test.sh` thresholds** — `MIN_MAIN_CARDS=60` instead of 20, `MIN_SIDE_CARDS=15`, export all 4 formats with `len(lines) >= expected` assertions, cached re-upload check, `$CI` autodetect for auto-teardown.
- [ ] **Fix `ci.yml:23` `continue-on-error: true`** on `lint` — at minimum for `safety check -r backend/requirements.txt` (CVE scanner was a silent advisory).
- [ ] **Fix Moxfield SB: prefix disagreement** — unit test `test_moxfield_export_structure` vs E2E `s1-happy-path.spec.ts:76` (`toMatch(/SB:/)`) disagree on whether the exporter emits `SB:` on sideboard lines. Pick one source of truth (the exporter code is canonical), update both tests accordingly.

## 🟡 Tech debt (post-merge follow-up PRs)

- [ ] **Consolidate the two `Settings` classes** — merge `backend/app/config.py` and `backend/app/core/config.py` into one. 12 import sites to update. See `docs/adr/0005-consolidate-settings-classes.md`.
- [ ] **Pin Docker base images by digest, not tag** — `python:3.11-slim`, `node:22-alpine`, `postgres:16-alpine`, `redis:7.4-alpine`, `otel/opentelemetry-collector-contrib:latest`, `jaegertracing/all-in-one:latest` all tag-pinned. Latest two (otel, jaeger) still use `:latest` in k8s.
- [ ] **Pin `torch` explicitly with `--index-url pytorch.org/whl/cpu`** — today's dep sweep auto-pulled NVIDIA CUDA bindings into the backend image (`nvidia-cublas`, `nvidia-cudnn-cu13`, `triton`, etc.), fattening it by ~2 GB. `backend/Dockerfile.optimized` already has the fix but is not wired up.
- [ ] **Reconcile `backend/Dockerfile` and `backend/Dockerfile.optimized`** — the optimized one has pre-cached pip layers + CPU-only torch + EasyOCR model preload but nothing uses it.
- [ ] **Cleanup untracked debris at repo root** — `server_working_backup/`, `test_improved_ocr.py`, `test_ocr_raw.py`, `test_parse_logic.py`, `analyze_validation_images.py`, `OCR_ANALYSIS_REPORT.html`, `UAT_GUIDE.html`, `PROJECT_INDEX.md` (untracked stale), `PR_BODY.md` (untracked stale), `validation_set/imported_from_old_project/`. Either `git add` or `git rm`.
- [ ] **Cross-workflow version consistency** — `ci.yml` uses Node 18 + Postgres 15, `e2e-tests.yml` uses mixed Node 18/20 + Postgres 16, etc. devops-engineer recommends a single `.ci-versions` or reusable workflow for env baselines.
- [ ] **k8s manifests are aspirational** — either promote to real deployment (kustomize overlays + External Secrets + digest-pinned images + CI deploy job that actually applies) or mark `k8s/` as a reference template and remove the implicit production claim.
- [ ] **One registry, one tagging policy** — `ci.yml` pushes to Docker Hub, `release.yml` pushes to GHCR, k8s references Docker Hub, cosign attestations nowhere. Consolidate.
- [ ] **SBOM attached to image via cosign** — currently SBOM is generated as a workflow artifact with 90-day retention, never attached to the pushed image.
- [ ] **Image size budget in CI** — no check caught today's ~2 GB torch/CUDA bloat.
- [ ] **Add `make doc-lint` target** — grep for `v2\.[0-3]\.` in root `.md` files, compare `main.py` `version="..."` against latest `CHANGELOG.md` entry, flag root `.md` older than 30 days. Surfaces drift before it ships.
- [ ] **Add `make bump-version VERSION=x.y.z`** — single-command rewrite of `main.py` + `README.md` + `CLAUDE.md` + `CHANGELOG.md` + `sub-agents/context/context-manager.json`. Single source of truth for versioning.

## 🔵 Decisions needed

- [ ] **`sub-agents/` directory** — currently untracked but load-bearing for the agent workflow (`sub-agents/context/context-manager.json` is 51 KB of project cartography). Either commit it with a `make refresh-context` target that regenerates on demand, OR delete the dependency and stop having agents read it. Picking the status quo (untracked but required) means every fresh clone has zero agent context.
- [ ] **release.yml dormant workflow** — keep as scaffolding for future tag-driven releases, or delete entirely until there's a real release cadence. Dormant since Aug 2025.
- [ ] **`passlib` abandoned upstream (last release 2020)** — replace with `bcrypt` or `argon2-cffi` before the Python 3.13 migration. Python 3.11 still works today but passlib uses the deprecated `crypt` module that 3.13 removed.
- [ ] **`metaphone` abandoned upstream (last release 2016)** — replace with `jellyfish` if we keep phonetic Scryfall matching. No security surface, no urgency.
- [ ] **8-month gap between Aug 2025 and Apr 2026** — is this the expected cadence (quarterly sprints) or a schedule bug? Project-planner flags this as the single most expensive methodology cost (every re-entry requires multi-agent context rebuild).

---

## How this file is maintained

- **New work**: add a `- [ ]` line with a short description, severity emoji, and (ideally) an acceptance criterion.
- **Done work**: copy the line to `DONE.md` under a dated section with the commit SHA, then remove from here. Never check `[x]` in place — `DONE.md` is the cumulative record.
- **Stale work**: if an item sits > 30 days without progress, either kill it with a rationale line in `DONE.md` or escalate to 🔴.
- **Blockers**: state them inline on the blocked item (`Blocks: X. Blocked by: Y`). No separate graph file.
- **Decision log**: decisions to *not* do something go in `docs/adr/` (see ADRs 0001-0005), not here.
