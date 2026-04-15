# ADR 0004 — Scryfall `/cards/collection` batch endpoint

- **Status**: Accepted
- **Date**: 2026-04-14
- **Commits**: PR #2 consolidation (Scryfall batch resolve migration)

## Context

The legacy Screen2Deck card-matching path was:

```python
async def normalize_deck(deck: ParsedDeck) -> NormalizedDeck:
    for card in deck.main:
        resolved = SCRYFALL.resolve(card.name)  # serial HTTP call per card
        ...
```

For a 60-card main + 15-card side, this issued **75 serial HTTPS calls**
to `https://api.scryfall.com/cards/named?fuzzy=<name>`. With the
project's rate-limit policy of 120ms between calls (over-cautious
relative to Scryfall's 10 req/s published guideline), a full deck
normalization took roughly 9 seconds of pure Scryfall time on top of
everything else.

Separately, the Scryfall REST API exposes a batch endpoint:

```
POST https://api.scryfall.com/cards/collection
{
  "identifiers": [{"name": "Lightning Bolt"}, {"name": "Counterspell"}, ...]
}
```

which accepts up to **75 identifiers per request** and returns all
matching cards in a single response.

## Decision

Add `SCRYFALL.batch_resolve(names: List[str])` that chunks the input
list into 75-element slices and issues one POST per chunk to
`/cards/collection`. `normalize_deck` now:

1. Collects all unique card names up front
2. Calls `batch_resolve` once (or N/75 times for very large lists)
3. Falls back to per-card `SCRYFALL.resolve()` for any name that the
   batch didn't match (misspellings, alternate faces, etc.)

The sync `batch_resolve` body is dispatched via `asyncio.to_thread` so
it doesn't block the event loop — previously `normalize_deck` was sync
inside an async handler and could stall incoming connections.

Also: the rate limit was relaxed from 120 ms → 100 ms per call to match
the published Scryfall guideline exactly (10 req/s), recovering ~17%
throughput on benchmark batches.

Also: added a mandatory `User-Agent: Screen2Deck/2.x (+github.com/…)`
header on every Scryfall call. Scryfall's 2024 policy change
([blog post](https://scryfall.com/blog/user-agent-and-accept-header-now-required-on-the-api-225))
throttles `python-requests/x.y` more aggressively and may block it
entirely.

## Consequences

### Positive

- **60-card deck normalization: ~9 s → ~500 ms** on the batch path
  (one chunked POST instead of 75 serial GETs).
- **Scryfall rate budget**: 75 resolves now cost 1 API call instead of
  75, leaving headroom for concurrent users.
- **Event loop health**: `asyncio.to_thread` wrapping means the sync
  sqlite + requests + sleep calls no longer block the async runtime.
- **Compliance**: the User-Agent header means we're playing by
  Scryfall's published rules and less likely to get IP-banned.

### Negative

- **Cache misses still fall back to per-card resolve**: if the OCR
  pipeline returns 60 card names and only 55 match via the batch
  endpoint, the other 5 still take 5 × 100ms = 500ms serial. Worst
  case is all 60 misspellings = 6 seconds, so we traded a reliable
  9 seconds for a variable 0.5–9 seconds.
- **Batch endpoint has slightly different response format**: some
  fields are absent vs the single-card endpoint, requiring a thin
  adapter in `batch_resolve` to normalize the shape.
- **Bulk `cards.collection` does NOT support fuzzy matching** —
  exact name or collector-number only. The fuzzy path still lives in
  the per-card fallback.

## Related

- Commit: PR #2 consolidation
- Scryfall API docs: https://scryfall.com/docs/api/cards/collection
- Scryfall User-Agent policy: https://scryfall.com/blog/user-agent-and-accept-header-now-required-on-the-api-225
