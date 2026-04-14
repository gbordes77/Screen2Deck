# Screen2Deck — Status of claims

This file draws a hard line between **what is verified** and **what is
projected** in the v2.4.0 codebase and its documentation. It exists so
that anyone (including the original author) coming back to this branch
can tell at a glance which numbers to trust and which to re-measure
before quoting them anywhere external.

**Last updated**: 2026-04-14

## ✅ Verified facts

Every item below is grounded in a command whose output you can
reproduce today.

| Claim | How to verify |
|---|---|
| The commits listed in `SESSION_NOTES.md` and the PR description exist with those hashes | `git log --oneline origin/main..refactor/consolidation-2026-04-14` |
| `backend/app/main_original.py`, `main_refactored.py`, `tasks.py`, `services/ocr_service.py`, `matching/scryfall_cache.py`, `pipeline/vision_fallback.py`, `migrate_to_production.py`, `webapp/lib/enhancedOcrServiceGuaranteed.ts` are deleted | `git show --name-status <commit>` or `ls` the paths |
| No Python file under `backend/app/` imports `pytesseract` or `tesseract` | `grep -RnE "^\s*(import\|from)\s+(py)?tesseract" backend/app/` |
| No Python file still references `python-jose` / `from jose` | `grep -RnE "from jose\|import jose" backend/` |
| `docker-compose.yml` uses `${POSTGRES_PASSWORD:?}` and `${JWT_SECRET_KEY:?}` substitution | read `docker-compose.yml` |
| The OpenAI API key that was in `.env:47` is **not** in git history | `git log --all -S 'sk-proj-'` returns empty |
| `gh pr checks 2` reported `Test Backend: SUCCESS` and `Test Frontend: SUCCESS` at least once after the latest fixes landed | `gh pr checks 2` |
| Every Python file I touched passes `ast.parse` | `python3 -c "import ast; ast.parse(open(PATH).read())"` for each file |
| The webapp passes `tsc --noEmit` with `strict: true` | `cd webapp && npx tsc --noEmit` |
| `−1173 LOC` removed in the cleanup commit | `git show --shortstat 824d4cb` |

## ⚠️ Projected / modelled — NOT measured

The following numbers appear in `README.md`, `CHANGELOG.md`,
`how-it-works.html`, `HANDOFF.md`, `CLAUDE.md`, and various PR
comments. They are **projections**, **search results**, or **theoretical
calculations** — not production measurements on this branch.

| Claim | Real source | What would be needed to verify |
|---|---|---|
| **p50 latency ~1.2 s** on the Vision-primary fast path | Output of the `performance-engineer` agent's modelling | Run `make smoke` against a warm Gemini key, time the `/status` poll until `completed` |
| **p95 latency ~2.7 s** on Vision-primary | Same as above | Run 100 uploads through `tools/benchmark.py`, compute p95 |
| **Accuracy +3–5 points** vs the EasyOCR path | Qualitative estimate from the OCR-research agent | Compare Vision-primary output vs EasyOCR output across the entire `validation_set/` with truth files |
| **~$0.00008 per image (Gemini)** | Arithmetic: `258 input tokens × $0.25 / 1M` — ignores output tokens | Run 100 uploads, read the token counts from Gemini's usage log, recompute |
| **60-card Scryfall resolve 7 s → 500 ms (14×)** | Theoretical: `60 × 120 ms vs 1 × 500 ms` — ignores DNS, TLS, JSON encoding | Time `normalize_deck` before and after the batch patch on the same deck |
| **Cache hit rate 50–80 %** | Copy-pasted from the pre-existing `README.md`, never re-measured | Enable Redis `MONITOR` during a load test, count `GET` hits vs misses |
| **Pipeline LOC −60 % on the fast path** | Eye-balled comparison of `process_ocr` function lengths | Diff `preprocess_variants + run_easyocr_best_of + parse_deck_sections` against the `run_vision_chain_structured` branch |
| **Gemini free tier: 250 req/day** on `gemini-3.1-flash-lite-preview` | Web search result from an aggregator site, not Google's own docs | Check https://ai.google.dev/gemini-api/docs/rate-limits for the current tier in **your** region and project |
| **Scryfall requires a User-Agent since 2024** | Web search mentioning the Scryfall blog post | Read https://scryfall.com/blog/user-agent-and-accept-header-now-required-on-the-api-225 directly |
| **CI is expected to pass after the last compose fix** | My best guess based on the specific failure mode | Wait for the next `gh run view` result |

## 🤷 Code that has never been executed

Everything in this column **compiles syntactically** but has not run
against real inputs on this branch:

- `backend/app/pipeline/vision_providers.py` — the entire
  `GeminiVisionProvider.extract_deck_structured` and
  `ClaudeVisionProvider.extract_deck_structured` code paths. In
  particular the exact signature of `GenerateContentConfig(response_mime_type=..., response_schema=...)` in `google-genai` and the `tool_choice={"type":"tool","name":"return_deck"}` form in the `anthropic` SDK are based on web search + SDK memory, not on a live import.
- `backend/app/matching/scryfall_client.py::batch_resolve` — new method,
  not exercised against Scryfall's real `/cards/collection`.
- `backend/app/business_rules.py::apply_mtgo_land_fix` — rewritten from
  the no-op stub to real redistribution logic, never fed a real MTGO
  screenshot's worth of entries.
- `backend/app/main.py::process_ocr` Vision-primary branch — never
  reached the `run_vision_chain_structured(img)` call in a running
  process.
- `backend/app/main.py::normalize_deck` — rewritten to go through
  `asyncio.to_thread(_resolve_all)`. Logic is straightforward but
  never traced end-to-end.
- `tests/unit/test_business_rules.py` and `tests/unit/test_exporters.py`
  — assertions were written against the real `backend.app` modules via
  `sys.path` hack, but `pytest` has never been run with the full
  backend requirements installed (ast-parse only).
- `tests/smoke_test.sh` — the shell script itself was syntax-checked
  (`bash -n`) but never executed.
- `backend/scripts/download_scryfall.py` — rewritten with `sys.path`
  fix and argparse, never run with the new code.
- The Docker Compose `env_file: [{ path: ..., required: false }]`
  long-form syntax — written from memory of the Compose 2.24+ changelog,
  not verified against the currently-installed compose version.

If any of these fails on a real run, the failure mode is usually
graceful — the Vision-primary path falls back to EasyOCR on exception,
the batch Scryfall fallback falls back to per-card `resolve`, the tests
just fail loudly in CI. Nothing silently corrupts data.

## 🔍 How to move items from "projected" to "verified"

1. **Smoke run**
   ```bash
   cp .env.example .env   # then fill POSTGRES_PASSWORD, JWT_SECRET_KEY, GEMINI_API_KEY
   python backend/scripts/download_scryfall.py
   make smoke
   ```
   If this turns green, about 8 of the items above move from the
   "projected" column to the "verified" column in one shot — stack
   boot, pipeline run, Scryfall resolution, MTGA export.

2. **Benchmark run**
   ```bash
   make bench-day0        # or: python tools/benchmark.py --images validation_set/images
   ```
   Produces a real `p50`, `p95`, and card-identification accuracy
   number against the truth files in `validation_set/truth/`.

3. **Cost measurement**
   Run the smoke test with `GEMINI_LOG_USAGE=true` (or read the
   response metadata) for 10 consecutive uploads. Sum the token counts.
   Multiply by the Gemini pricing in your region. That's the real cost
   per image.

4. **Update this file** as claims move from one column to the other.
