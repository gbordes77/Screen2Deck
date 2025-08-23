# CLAUDE.md - Screen2Deck AI Assistant Guide

This file provides guidance to Claude Code when working with the Screen2Deck repository.

## Project Status: Production Ready (v2.3.0)

**Latest Update**: 2025-08-23 - Documentation cleanup and standardization
- Removed excessive defensive tone from all documentation
- Added mandatory session tracking system
- Simplified from 672 to 117 lines

**Previous Updates**:
- 2025-08-19: Online-only operation with Scryfall API integration
- EasyOCR models downloaded on-demand (~64MB on first run)
- No offline capabilities - requires internet connection
- Core services: Redis, PostgreSQL, Backend (FastAPI), Frontend (Next.js)

## Current Technical Notes

### Documentation State
- ✅ Cleaned and professional tone
- ✅ Session tracking system implemented
- ⚠️ PROOF_SUMMARY.md might be redundant (consider removal)
- ⚠️ Some test scripts might be duplicates

### Important Discovery
- Documentation was overly defensive with excessive "NOT FAKE" claims
- This made the project appear suspicious rather than professional
- Simple, factual documentation is more credible

## OCR Processing Pipeline

The OCR flow is critical to the application's functionality:

```
1. IMAGE UPLOAD → Validation and storage
2. PREPROCESSING → 4 variants (Original, Denoised, Binarized, Sharpened)
3. EASYOCR → Primary OCR engine (multi-pass with 85% confidence threshold)
4. CONFIDENCE CHECK → If <62%, optional Vision API fallback
5. SCRYFALL VALIDATION → Mandatory API verification for all cards
6. EXPORT → Multiple formats (MTGA, Moxfield, Archidekt, TappedOut)
```

**Important**: This project uses EasyOCR exclusively. Tesseract is not supported.

## Project Structure

```
/
├── backend/           # FastAPI backend
│   ├── app/
│   │   ├── main.py   # API endpoints
│   │   ├── pipeline/ # OCR processing
│   │   ├── matching/ # Card resolution
│   │   └── exporters/# Export formats
├── webapp/           # Next.js frontend
│   ├── app/         # App router pages
│   └── lib/         # Utilities
├── tests/           # Test suites
├── tools/           # Benchmarking tools
└── docker-compose.yml
```

## Key Configuration

### Database
- Use `psycopg[binary]` (never asyncpg)
- PostgreSQL URL: `postgresql+psycopg://`
- Docker PostgreSQL: Port 5433 externally (5432 internally)

### Environment Variables
```env
ALWAYS_VERIFY_SCRYFALL=true  # Never disable
OCR_MIN_CONF=0.62           # Minimum OCR confidence
FEATURE_TELEMETRY=false      # Disable in dev
```

## Development Commands

```bash
# Quick start
make up              # Start all services
make test-online     # Run E2E tests
make health         # Check health

# Testing
make test           # Unit + integration tests
make bench-day0     # Performance benchmarks
make golden         # Validate export formats
make parity         # Check Web/Discord parity

# Development
make logs           # View logs
make shell-backend  # Backend shell
make down          # Stop services
```

## API Endpoints

- `POST /api/ocr/upload` - Upload image for OCR
- `GET /api/ocr/status/:jobId` - Check processing status
- `POST /api/export/:format` - Export to specific format
- `GET /health` - Health check

## Performance Targets

- Accuracy: ≥85% (fuzzy match)
- P95 Latency: ≤5s
- Cache Hit Rate: ≥50%
- Memory Usage: <500MB per instance

## Common Issues & Solutions

1. **ModuleNotFoundError 'opentelemetry'**: Set `FEATURE_TELEMETRY=false`
2. **Port 5432 already allocated**: Use port 5433 for Docker PostgreSQL
3. **ARM64/M1/M2 Docker build fails**: Remove x86-specific packages from Dockerfile
4. **Performance on CPU**: ~9s average (GPU required for <3s performance)
5. **First run slow**: EasyOCR downloads models (~64MB) on first use

## Testing

The project includes comprehensive testing:
- Unit tests with MTG edge cases (DFC, Split, Adventure cards)
- Integration tests for API endpoints
- E2E tests with Playwright (14 test suites)
- Golden tests for export format validation
- Parity tests for Web/Discord consistency

Run `make test` for the complete test suite.

## Code Style

- Backend: Python with type hints
- Frontend: TypeScript with React/Next.js
- All card names validated through Scryfall API
- Follow existing patterns in codebase

## 📝 IMPORTANT: Session Tracking Requirements

### Files to Update at End of Each Session

1. **HANDOFF.md** - Primary session summary
   - What was done today
   - Current state (working/broken)
   - Blockers and issues
   - Next steps for next team

2. **CLAUDE.md** - Technical notes for AI
   - Latest changes with date
   - Current issues/blockers
   - Critical warnings discovered
   - Keep last 3-5 updates

3. **README.md** - Public documentation
   - Update version if major change
   - Add new features to feature list
   - Update performance metrics if improved
   - Keep clean and professional

4. **SESSION_NOTES.md** (Optional) - Detailed session history
   - Create if you want session-by-session history
   - More detailed than HANDOFF.md
   - Include commands run, errors encountered

### Session End Checklist
- [ ] Update HANDOFF.md with today's work
- [ ] Add technical notes to CLAUDE.md
- [ ] Update README.md if public changes
- [ ] Commit with clear message
- [ ] Note any unresolved issues