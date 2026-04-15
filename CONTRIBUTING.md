# Contributing to Screen2Deck

Thanks for taking the time to contribute. Screen2Deck is a production MTG card
OCR pipeline (FastAPI backend + Next.js webapp + Discord bot), and every PR
helps tighten the loop between image upload and a clean, validated deck list.

## Ground rules

- **One logical change per PR.** Refactors, bug fixes and new features should
  each land as separate PRs so we can bisect cleanly if something regresses.
- **Scryfall is the source of truth.** Any card name coming out of OCR must be
  validated through the Scryfall API before being returned to the client or
  written to an export file.
- **EasyOCR only.** Tesseract is not supported. CI enforces this with an
  anti-Tesseract scan in `.github/workflows/proof-tests.yml`.
- **No secrets in git.** Use `.env` (already git-ignored) and let CI inject
  secrets via GitHub Actions environments.
- **Don't add backwards-compatibility shims.** If you rename or remove something,
  update every caller in the same PR.

## Development loop

```bash
# Start the full stack
make up

# Run unit and integration tests
make test

# Run the E2E suite (requires the stack to be up)
make test-online

# Run the benchmark against validation_set/
make bench-day0

# Stop everything
make down
```

Backend code lives in `backend/`, the Next.js webapp in `webapp/`, and the
Discord bot in `discord/`. See `CLAUDE.md` for the AI-assistant development
guide and `docs/ARCHITECTURE.md` for the high-level picture.

## Code style

- **Python**: type hints on public functions, `ruff` + `black` formatting,
  pytest for tests. Async on the FastAPI path, sync only in Celery workers.
- **TypeScript**: `strict: true` in tsconfigs, React Server Components where
  possible, no `any`. Use the `ApiError` class for HTTP errors, not raw
  `throw new Error(...)`.
- **Commits**: follow Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`,
  `refactor:`, `test:`, `ci:`, `perf:`) so that `CHANGELOG.md` stays usable.

## Pull requests

1. Fork and branch from `main` (or the active release branch).
2. Run `make test` locally before pushing.
3. Open a PR with a clear title and a description that explains the **why**,
   not just the **what**.
4. Reference the issue(s) your PR closes with `Closes #123`.
5. Watch the CI run — all jobs must be green before review.

## Reporting bugs

Open a GitHub issue with:

- A minimal repro (ideally a failing test or a command line).
- The image you uploaded if the issue is OCR-related (or a similar public
  screenshot if the original contains sensitive data).
- The full backend log around the failure.
- Your environment: OS, Python version, Docker version, GPU vs CPU.

## Security

Do **not** open a public GitHub issue for security problems. Email
`security@screen2deck.local` (or open a private security advisory on GitHub)
with the details and a suggested remediation. We'll acknowledge within 48h.
