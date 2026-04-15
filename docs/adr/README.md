# Architecture Decision Records

ADRs capture the **why** behind significant architectural choices made on
Screen2Deck, following [Michael Nygard's template](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions).

## Format

Each ADR is a short markdown file with four sections:

- **Context** — what problem we faced and what constraints shaped the choice
- **Decision** — what we picked
- **Consequences** — what this gets us and what it costs us
- **Status** — Proposed / Accepted / Deprecated / Superseded by ADR N

## Numbering

ADRs are numbered in the order they were accepted. Never renumber. When an
ADR is superseded, mark it as such and add a new ADR that points back.

## Index

| # | Title | Status |
|---|---|---|
| 0001 | [OpenAI Vision → Gemini + Claude Vision](0001-openai-to-gemini-vision-chain.md) | Accepted (2026-04-14) |
| 0002 | [python-jose → PyJWT migration](0002-python-jose-to-pyjwt.md) | Accepted (2026-04-14) |
| 0003 | [Vision-primary fast path with structured JSON schema](0003-vision-primary-fast-path.md) | Accepted (2026-04-14) |
| 0004 | [Scryfall `/cards/collection` batch endpoint](0004-scryfall-batch-endpoint.md) | Accepted (2026-04-14) |
| 0005 | [Consolidate two `Settings` classes](0005-consolidate-settings-classes.md) | Proposed (2026-04-15) |
