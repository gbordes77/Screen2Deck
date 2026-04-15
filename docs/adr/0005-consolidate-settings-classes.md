# ADR 0005 — Consolidate two `Settings` classes into one

- **Status**: Proposed (2026-04-15)
- **Target landing**: follow-up PR after PR #2 merges
- **Related commits**: `81b4ab6 chore: stop-the-bleeding` (defaults aligned,
  full consolidation deferred)

## Context

Screen2Deck currently has **two competing `Settings` classes** that half
the codebase each imports from:

- `backend/app/config.py` — plain Python class with `os.getenv(...)` for
  every field. Used by:
  - `app/cache_manager.py`
  - `app/core/rate_limit.py`
  - `app/core/retention.py`
  - `app/core/circuit_breaker.py`
  - `app/core/idempotency.py`
  - `app/pipeline/ocr.py`
  - `app/pipeline/preprocess.py`
  - `app/pipeline/vision_providers.py`
  - `app/matching/scryfall_client.py`
  - `app/api/health.py`
  - `backend/scripts/download_scryfall.py`
  - `backend/tests/conftest.py`

- `backend/app/core/config.py` — Pydantic `BaseSettings` with
  `Field(..., env="X")` validators. Used by:
  - `app/main.py`
  - `app/auth.py`
  - `app/db/database.py`
  - `app/core/auth_middleware.py`
  - `app/core/job_storage.py`
  - `app/routers/auth_router.py`
  - `app/routers/health.py`
  - `app/routers/gdpr.py`
  - `app/api/websocket.py`

Neither is a strict superset of the other:

**Only in `config.py`** (not in `core/config.py`):
`SCRYFALL_DB`, `SCRYFALL_BULK_PATH`, `SCRYFALL_TIMEOUT`, `GDPR_ENABLED`,
`DATA_RETENTION_*` (5 fields), `ENABLE_ANALYTICS`, `ENABLE_TRACKING`,
`REQUIRE_CONSENT`, `HEALTH_EXPOSE_INTERNAL`, `HEALTH_ALLOWED_IPS`,
`HEALTH_REQUIRE_AUTH`

**Only in `core/config.py`** (not in `config.py`):
`JWT_SECRET_KEY` (required field), `JWT_ALGORITHM`,
`ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`,
`API_KEY_PREFIX`, `DATABASE_URL`, `DATABASE_POOL_SIZE`,
`DATABASE_MAX_OVERFLOW`, `REDIS_PASSWORD`, `REDIS_POOL_SIZE`,
`ENABLE_METRICS`, `METRICS_PORT`, `ENABLE_TRACING`, `JAEGER_*`,
`CORS_*`, `RATE_LIMIT_*`, `FEATURE_WEBSOCKET`, `FEATURE_GRAPHQL`,
`FEATURE_ASYNC_PROCESSING`

The divergence was caught in the 2026-04-15 methodology audit because
default values **drifted silently** between the two classes: commit
`0d2846a` updated `GEMINI_MODEL` to `gemini-2.5-flash` in `config.py`
but left `core/config.py` on `gemini-3.1-flash-lite-preview` (the
saturated preview model). The smoke test only passed because
`docker-compose.yml` forced `GEMINI_MODEL` via env var, masking the
Python-level drift.

Commit `81b4ab6` aligned the three Vision defaults
(`GEMINI_MODEL`, `VISION_PRIMARY`, `ENABLE_VISION_FALLBACK`) in both
files and added warning comments at the top of each pointing at this
ADR, but the full merge was deferred.

## Decision

In a single follow-up PR:

1. **Pick `core/config.py`** (Pydantic BaseSettings) as the canonical
   Settings class. Rationale: Pydantic validation + `Field(..., env="X")`
   + `.env` file auto-loading + type coercion are all strictly better
   than the plain `os.getenv` pattern.

2. **Add the 16 "only in config.py" fields** to `core/config.py` as
   `Field(..., env="X")` entries with their current defaults.

3. **Rewrite `config.py` as a thin shim** that re-exports `Settings`,
   `get_settings`, and the module-level `settings` variable from
   `core/config.py`:

   ```python
   from .core.config import Settings, get_settings, settings  # noqa: F401
   ```

   This keeps all existing `from .config import get_settings` imports
   working without touching any of the 12 call sites. The shim can be
   deleted in a later PR once every caller has been updated to
   `from .core.config import ...` for clarity.

4. **Add a runtime assertion** in `main.py` startup that calls
   `get_settings()` from both paths and asserts identity — fails loud
   if the shim accidentally gets un-shimmed.

5. **Delete `config.py` entirely** in a third follow-up PR once every
   import has been migrated.

## Consequences

### Positive

- **One source of truth** for every env var + default + validation
  rule. No more silent drift.
- **Pydantic benefits** (type coercion, `.env` loading, field
  validators) available to the 12 call sites that currently don't
  get them.
- **Smaller delta** than a full rename migration because step 3 is
  a re-export shim, not a file-by-file import rewrite.
- **Reversible**: if the Pydantic BaseSettings class causes a boot
  regression, the shim can be rolled back to the old plain class.

### Negative

- **One big PR with ~16 field additions** — reviewer has to diff
  two Settings definitions side-by-side to check defaults.
- **Tests need re-running** end-to-end because the env var loading
  order changes: Pydantic reads `.env` at instantiation time, plain
  `os.getenv` reads at class definition (import) time.
- **`JWT_SECRET_KEY` becomes required** when `core/config.py` is the
  canonical class — right now `config.py` has no such requirement.
  This will break any dev environment that was relying on the plain
  class's silent default. The migration PR should add a clear error
  message and update `.env.example`.
- **Pydantic BaseSettings has edge cases** around list parsing
  (`CORS_ORIGINS` has a custom `field_validator` for JSON parsing)
  that the plain class doesn't hit. Need to verify the `field_validator`
  still runs under pydantic-settings 2.x.

## Out of scope for this ADR

- Whether to split Settings into multiple domain-specific classes
  (`VisionSettings`, `DatabaseSettings`, etc.). Current answer: no,
  keep one class for now — splitting adds more import sites without
  reducing drift risk.
- Whether to move env var management to a separate library like
  `dynaconf` or `python-decouple`. No — Pydantic Settings is
  sufficient and already a transitive dep.

## Related

- Commit `81b4ab6` — defaults aligned, full merge deferred
- Commit `0d2846a` — the commit that exposed the drift
- ADR 0003 (Vision-primary fast path) — the feature that exposed
  the drift via its env var defaults
