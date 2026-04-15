# ADR 0003 — Vision-primary fast path with structured JSON schema

- **Status**: Accepted
- **Date**: 2026-04-14 (feature), 2026-04-15 (deployment fix)
- **Commits**: PR #2 consolidation + `009e02b fix(deploy): wire Vision-primary fast path in docker-compose`

## Context

The legacy Screen2Deck OCR pipeline was:

```
image → preprocess (4 variants) → EasyOCR best-of → confidence check
      → [if low conf] Vision fallback → regex parser (parse_deck_sections)
      → Scryfall resolution → normalize → export
```

With the OpenAI → Gemini migration (ADR 0001), the Vision step became
cheap enough (~$0.0001 per call) and accurate enough to replace the
entire preprocess + EasyOCR + regex chain for clean screenshots.

Two further facts made this attractive:

1. Gemini's `response_json_schema` and Anthropic's `tool_choice`-forced
   tool use both return typed JSON directly, killing the fragile regex
   parser on the happy path.
2. EasyOCR's first-run cost is ~64 MB of model download + ~9 seconds of
   CPU work per image, which dominates the latency budget on non-GPU
   deployments.

## Decision

Add a **Vision-primary fast path** to `backend/app/main.py:327`, gated on
two env vars:

- `ENABLE_VISION_FALLBACK=true` — global on/off for the Vision LLM path
- `VISION_PRIMARY=true` — route Vision FIRST, EasyOCR becomes the hard
  fallback

When both are true:

```python
if settings.ENABLE_VISION_FALLBACK and getattr(settings, "VISION_PRIMARY", False):
    structured = await asyncio.to_thread(run_vision_chain_structured, img)
    if structured and (structured.get("main") or structured.get("side")):
        # build DeckSections directly from typed JSON, skip EasyOCR + regex
        ...
```

`run_vision_chain_structured` iterates over `VISION_PROVIDER` in order and
returns the first provider's `{main, side}` dict. If every provider fails
(no key, 503, schema error, …), the function returns `None` and the code
falls through to the legacy EasyOCR path with zero special-case logic.

Defaults:

- `config.py` / `core/config.py`: both true (aligned in commit `81b4ab6`)
- `docker-compose.yml` backend environment: both true by default via
  `${VAR:-true}` substitution (wired in commit `009e02b`)

## Consequences

### Positive

- **Modeled P95 latency drop**: 4.1 s → 2.7 s for VISION_PRIMARY=true
  (image processing bypassed entirely).
- **Accuracy gain**: +3–5 percentage points on fuzzy-match rate vs the
  EasyOCR + regex parser path, because Gemini's JSON output doesn't
  split card names on whitespace or strip punctuation.
- **Zero regression surface for operators without Gemini**: the chain
  returns `None` on empty provider list and main.py falls back to the
  legacy EasyOCR path, so unconfigured deployments still work.
- **The regex parser (`parse_deck_sections`) is now dead code on the
  happy path**, simplifying MTGO 60+15 handling and split-card normalization.

### Negative

- **Silent feature flag**: the v2.4.0 release shipped with this feature
  committed to `main.py` but **not wired in docker-compose.yml**. Every
  Docker deployment between v2.4.0 and commit `009e02b` (2026-04-15)
  silently ran EasyOCR-only, which undermined the entire point of
  landing the feature. The fix in `009e02b` forwards the env vars
  with `${VAR:-true}` defaults; the smoke test confirmed end-to-end
  that the fast path now fires.
- **Two Settings classes**: the feature flag was defined in
  `backend/app/config.py` (`VISION_PRIMARY` class attribute) but not
  initially in `backend/app/core/config.py`. Half the codebase imports
  from each — see ADR 0005 for the consolidation plan. Alignment of
  the defaults happened in commit `81b4ab6`.
- **Cost model depends on volume**: at 1000 req/day the Vision-primary
  path costs ~$0.08/day on Gemini 2.5 Flash. At 100k req/day (unlikely
  but possible) it's $8/day, which is still cheap but no longer free.
  A future throttle or cache (see PLAN.md tech-debt "Cache Redis by
  SHA-256 hash") may be needed.
- **Vendor lock-in**: the fast path only works with providers that
  support structured output via JSON Schema / tool use. If Gemini
  ever removes `response_json_schema`, the provider falls through to
  `extract_deck` (plain text) and we lose the typed output.

## Related

- ADR 0001 (OpenAI → Gemini/Claude) — prerequisite
- Commit `0d2846a` (google-genai 1.x migration, fixes
  `response_schema` → `response_json_schema` canonical field name)
- Commit `009e02b` (the actual wiring in docker-compose.yml)
- Commit `81b4ab6` (Settings default alignment)
