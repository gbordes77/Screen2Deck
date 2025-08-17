# MTG Deck Scanner — Documentation Pack
_Date: 2025-08-16_

This pack documents the whole project end-to-end (backend FastAPI, OCR pipeline, Scryfall verification, webapp Next.js, Docker, CI, runbooks).

## Files
- 01-setup.md — local & Docker setup, first run, smoke tests
- 02-architecture.md — system architecture, flows, data model
- 03-config.md — environment variables & flags
- 04-api.md — REST endpoints & schemas
- 05-pipeline.md — preprocessing, OCR multi-pass, fallbacks, Scryfall canonicalization (ALWAYS ON)
- 06-exports.md — MTGA / Moxfield / Archidekt / TappedOut
- 07-error-taxonomy.md — error codes and meanings
- 08-runbooks.md — incidents & resolutions
- 09-validation.md — accuracy & latency validation plan
- 10-security.md — security, rate-limits, CORS, data handling
- 11-deployment.md — Docker Compose, production notes
- 12-ci-cd.md — GitHub Actions pipeline
- 13-adr-0001-ocr.md — OCR choice
- 14-adr-0002-ui.md — Frontend/UX choice
- 15-troubleshooting.md — common issues
- 16-contributing.md — style, testing, PRs
- 17-faq.md — quick answers
