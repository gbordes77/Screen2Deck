# ADR 0001 — OpenAI Vision → Gemini + Claude Vision chain

- **Status**: Accepted
- **Date**: 2026-04-14
- **Commit**: `b134dd1 feat(vision): migrate from OpenAI to Gemini + Claude fallback chain`

## Context

Screen2Deck v2.3.0 used OpenAI's Vision API (`gpt-4-vision-preview`) as the
low-confidence fallback for EasyOCR. The integration shipped in
`backend/app/pipeline/vision_fallback.py` with `openai==1.3.0` pinned.

By early 2026 several pressures converged:

1. **Cost**: GPT-4 Vision calls were ~$0.01–0.02 per image at typical deck
   screenshot sizes, which mapped to ~$10–20/day at 1000 req/day. Gemini 2.5
   Flash was priced at $0.25/$1.50 per 1M input/output tokens — roughly 2
   orders of magnitude cheaper for the same workload.
2. **Rate limits**: OpenAI's free-tier vision quota was too restrictive for
   continuous smoke testing; we kept hitting 429s in CI.
3. **Structured output**: Gemini's `response_schema` / `response_json_schema`
   and Anthropic's `tool_choice`-forced tool use both give typed JSON
   guarantees. OpenAI's equivalent (Structured Outputs, released late 2024)
   was available but required adopting a second schema library on top of the
   existing pipeline's Pydantic models.
4. **Discord-bot parallel**: the sister Discord bot had already moved to
   Gemini for similar cost reasons, and running two vendors side-by-side
   doubled the surface area for secret management, credential rotation,
   and error handling.

## Decision

Drop the OpenAI integration entirely. Replace it with a provider chain:

1. **Primary**: Gemini 2.5 Flash (stable GA) via the `google-genai` Python
   SDK ≥1.73.1. Returns structured `{main, side}` JSON via
   `response_json_schema` in `GenerateContentConfig`.
2. **Fallback**: Claude Haiku 4.5 via the `anthropic` Python SDK ≥0.95.0.
   Uses `tool_choice={"type": "tool", "name": "return_deck"}` to force a
   tool call with a JSON Schema `input_schema`.

Both providers are wrapped behind a `VisionProvider` ABC in
`backend/app/pipeline/vision_providers.py`. The chain is configured via the
`VISION_PROVIDER=gemini,claude` env var (comma-separated, first available
wins).

Unavailable providers (missing API key, SDK not importable) are silently
skipped, so operators without an Anthropic key still work.

## Consequences

### Positive

- **~100× cost reduction** for the Vision fallback path (modeled).
- **No more OpenAI dependency** — `openai==1.3.0` dropped from
  `requirements.txt`.
- **Typed JSON output** removes the fragile regex parser from the happy path.
- **Easier CI** — Gemini's free tier is generous enough to run smoke tests
  on every PR without quota concerns.
- **Clean provider abstraction** — adding a third provider (e.g. xAI Grok
  Vision) is a ~50 LOC subclass, not a pipeline rewrite.

### Negative

- **SDK maturity**: the `google-genai` Python SDK jumped from 0.8 to 1.x
  between session dates, and the structured-output field was renamed from
  `response_schema` to `response_json_schema` for raw JSON Schema dicts.
  This bit us and required a follow-up commit (`0d2846a`).
- **Preview model trap**: the initial default was
  `gemini-3.1-flash-lite-preview`, which is heavily oversubscribed on
  Google's side and consistently returns 503 UNAVAILABLE. Switched to
  stable `gemini-2.5-flash` in commit `0d2846a`.
- **Two vendor surfaces instead of one**: we now maintain keys for Gemini
  AND Anthropic. The chain falls back gracefully if one is missing, but
  the operational surface is larger than the single-vendor OpenAI path.
- **Anthropic API access is not free** — Claude Pro/Max subscriptions do
  NOT include API access; operators need a separate billing account at
  console.anthropic.com. Our default chain lists Claude second so most
  users don't hit this.

## Related

- ADR 0003 (Vision-primary fast path) — depends on this decision
- ADR 0005 (Consolidate Settings classes) — the two Settings classes
  captured divergent Gemini model defaults
- Commit `0d2846a` — migration to google-genai 1.73.1 + default model swap
