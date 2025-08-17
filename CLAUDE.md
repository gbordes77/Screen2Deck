# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🚨 CRITICAL OCR FLOW - NEVER MODIFY WITHOUT AUTHORIZATION 🚨

### ⚠️ MANDATORY OCR PROCESSING FLOW ⚠️
```
┌──────────────────────────────────────────────────────────────┐
│ 🔴 DO NOT BYPASS THIS FLOW - BREAKING IT CAUSES REGRESSIONS │
└──────────────────────────────────────────────────────────────┘

1. IMAGE UPLOAD
      ↓
2. 🖼️ PREPROCESSING (4 VARIANTS)
      ├─ Original image
      ├─ Denoised variant
      ├─ Binarized variant
      └─ Sharpened variant
      ↓
3. 🐍 EASYOCR (PRIMARY ENGINE) ← MUST BE FIRST!
      ├─ Multi-pass on all variants
      ├─ Early termination at 85% confidence
      └─ Returns mean confidence score
      ↓
4. CONFIDENCE CHECK
      ├─ IF > 62% → Continue to Scryfall
      └─ IF < 62% AND Vision enabled → Use Vision as FALLBACK ONLY
      ↓
5. 🔍 SCRYFALL VALIDATION (MANDATORY)
      ├─ Local fuzzy matching
      ├─ Offline cache lookup
      └─ Online API fallback
      ↓
6. RETURN RESULTS
      ├─ Mainboard cards
      └─ Sideboard cards (if detected)
```

### ❌ NEVER DO THIS:
- Skip EasyOCR and use another OCR engine
- Disable Scryfall validation (`ALWAYS_VERIFY_SCRYFALL=false`)
- Bypass the preprocessing pipeline
- Ignore confidence thresholds
- Use Tesseract (NEVER, under any circumstances)

### ✅ ALWAYS DO THIS:
- EasyOCR runs FIRST (it's the primary engine)
- Scryfall validation for EVERY card
- Maintain all 4 preprocessing variants
- Respect the confidence threshold (62%)
- Support all 4 export formats

## Project Overview

**Screen2Deck v1.0** - OCR-based web application for converting Magic: The Gathering deck images to various digital formats (MTGA, Moxfield, Archidekt, TappedOut).

**Current Status**: 🔧 In Development - Requires security hardening and performance optimization before production  
**Performance Score**: 4.25/10 - See analysis report for details

The system uses EasyOCR for text extraction and Scryfall for mandatory card name validation.

## 📚 DOCUMENTATION RULES - IMPORTANT

### Documentation Structure
```
/                           # Root documentation
├── CLAUDE.md              # This file - AI guidance
├── README.md              # Project overview
├── START.sh               # Startup script with instructions
├── TEST_INSTALL.sh        # Installation verification
└── MTG_Deck_Scanner_Docs_v2/  # Detailed documentation
    ├── 00-INDEX.md        # Documentation index
    ├── 01-setup.md        # Setup guide
    ├── 02-architecture.md # Architecture details
    ├── 03-config.md       # Configuration guide
    └── ...                # Additional docs
```

### Documentation Rules
1. **NE JAMAIS créer de doublons** - Check if document exists before creation
2. **Update existing docs** rather than creating new ones
3. **Maintain consistency** - Use same version numbers everywhere
4. **Add deprecation warnings** on outdated documents

## Commands

### Development
```bash
# Start entire stack with Docker
docker compose up --build

# Alternative: Use the start script
./START.sh

# Test installation
./TEST_INSTALL.sh

# Frontend only (Next.js)
cd webapp && npm run dev

# Backend only (FastAPI)
cd backend && uvicorn app.main:app --reload --port 8080

# Download/update Scryfall bulk data
cd backend && python scripts/download_scryfall.py
```

### Docker Commands
```bash
# Development mode
docker compose up -d              # Start all services
docker compose logs -f            # View logs
docker compose down              # Stop services

# Production deployment (when available)
docker compose -f docker-compose.prod.yml up -d
```

### Testing Commands
```bash
# Backend tests (when implemented)
cd backend && pytest

# Frontend tests (when implemented)
cd webapp && npm test

# Validation with real images
# Place test images in decklist-validation-set/
python backend/tests/test_validation_set.py
```

### Ports
- Frontend: http://localhost:3000
- Backend API: http://localhost:8080
- Redis: localhost:6379

## Architecture Overview

### Technology Stack
- **Frontend**: Next.js 14, React 18, TypeScript, TailwindCSS
- **Backend**: FastAPI, Python 3.8+, Pydantic, uvicorn
- **OCR Engine**: EasyOCR (GPU-accelerated when available)
- **External Services**: Scryfall API (card validation), Redis (optional cache)
- **Infrastructure**: Docker, Docker Compose

### Data Flow
1. User uploads image via web UI
2. Image preprocessed into 4 variants (original, denoised, binarized, sharpened)
3. EasyOCR processes all variants with early termination
4. Card names extracted with regex patterns
5. Names validated via Scryfall (fuzzy match + API)
6. Results cached and returned with export options
7. Multiple export formats available (MTGA, Moxfield, Archidekt, TappedOut)

### Key API Endpoints
- `POST /api/ocr/upload` - Upload image for OCR processing (returns jobId)
- `GET /api/ocr/status/:jobId` - Check OCR processing status
- `POST /api/export/:format` - Export deck to specific format

### OCR Processing Pipeline
1. **Image Upload** → `main.py:upload_image()` validates and stores image
2. **Preprocessing** → `pipeline/preprocess.py:preprocess_variants()` creates 4 image variants
3. **OCR Execution** → `pipeline/ocr.py:run_easyocr_best_of()` runs OCR with early termination (≥85%)
4. **Text Parsing** → `main.py` extracts quantities and card names
5. **Card Resolution** → Two-phase validation:
   - Local fuzzy matching via `matching/fuzzy.py:score_candidates()`
   - **MANDATORY** Scryfall verification via `matching/scryfall_client.py:resolve()`
6. **Export Generation** → Format-specific exporters in `exporters/` directory

### Key Components

**Backend (FastAPI)**:
- `app/main.py`: API endpoints, request handling, orchestration
- `app/config.py`: Environment configuration (Settings class)
- `app/pipeline/`: OCR and image preprocessing
- `app/matching/`: Card name resolution (fuzzy + Scryfall)
- `app/exporters/`: Format-specific export logic
- `app/models.py`: Pydantic models for data validation
- `app/cache.py`: Job storage (in-memory, Redis optional)

**Frontend (Next.js 14)**:
- `app/page.tsx`: Upload interface
- `app/result/[jobId]/page.tsx`: Results display with progressive polling
- `lib/api.ts`: API client functions

## Environment Configuration

### Required Environment Variables
- `ALWAYS_VERIFY_SCRYFALL=true` - **NEVER disable this**
- `OCR_MIN_CONF=0.62` - Minimum OCR confidence threshold
- `OCR_MIN_LINES=10` - Minimum lines for valid OCR

### Optional Environment Variables
- `ENABLE_VISION_FALLBACK=false` - Enable OpenAI Vision API fallback
- `USE_REDIS=false` - Enable Redis caching (recommended for production)
- `MAX_IMAGE_MB=8` - Maximum upload size in MB
- `FUZZY_MATCH_TOPK=5` - Number of fuzzy match candidates
- `ENABLE_SUPERRES=false` - Enable super-resolution preprocessing

## Testing & Validation

⚠️ **IMPORTANT**: Production deployment requires completing these validation steps.

### Current Testing Status
- **Backend**: Basic validation tests with real images
- **Frontend**: No automated tests yet
- **E2E**: Manual testing only
- **Performance**: ~2-8s per image (needs optimization)
- **Security**: Critical vulnerabilities identified

### Required Before Production
1. Fix critical security issues (CORS, rate limiting, authentication)
2. Implement comprehensive test suite
3. Optimize performance (target < 2s per deck)
4. Test with 20+ real MTGA/MTGO screenshots
5. Document real performance metrics
6. Complete security audit remediation

### Test Images
Available in `decklist-validation-set/`:
- MTGA deck lists
- MTGO deck lists  
- MTGGoldfish exports
- Physical card photos
- Web screenshots

## OCR Optimization Rules

1. **Multi-variant Processing**: Always process 4 image variants for best results
2. **Early Termination**: Stop at 85% confidence to save processing time
3. **GPU Acceleration**: Automatically enabled when CUDA available (3-5x faster)
4. **Language Models**: 4 languages loaded (EN, FR, DE, ES) - consider reducing for memory
5. **Fuzzy Matching**: LRU cached with metaphone for 30-40% speed improvement
6. **Confidence Threshold**: 62% minimum for reliable results
7. **Progressive Polling**: Frontend polls at increasing intervals (500ms → 2s)

## Development Workflow

1. Frontend runs on port 3000, proxies `/api` calls to backend on port 8080
2. Backend validates environment on startup
3. All components support hot reload in development
4. Use `./START.sh` for automated startup with configuration
5. First run downloads ~100MB Scryfall bulk data
6. GPU acceleration automatic if CUDA available
7. Test with real images from `decklist-validation-set/`

## Features

- **OCR Processing**: EasyOCR with 4-variant preprocessing
- **Multi-Format Export**: MTGA, Moxfield, Archidekt, TappedOut
- **Smart Caching**: LRU cache for fuzzy matching
- **Performance**: Currently 2-8s (optimizable to < 2s)
- **Validation**: Mandatory Scryfall verification
- **Rate Limiting**: Per-IP protection against abuse

## Security Considerations

### Current Security Measures
- CORS restricted to specific origins
- Per-IP rate limiting with configurable limits  
- File upload validation (type and size)
- Input sanitization in OCR pipeline

### Critical Security Issues (Must Fix)
- Add authentication/authorization system
- Implement proper job access control
- Add security headers (CSP, HSTS, etc.)
- Run Docker containers as non-root
- Validate all external API responses

## Performance Optimizations

### Implemented Optimizations
- GPU acceleration (3-5x faster when available)
- Early termination at 85% confidence
- LRU caching in fuzzy matching (30-40% improvement)
- Progressive polling intervals (60-70% fewer API calls)

### Pending Optimizations
- Implement async job processing
- Add Redis caching layer
- Optimize image preprocessing pipeline
- Implement connection pooling for Scryfall
- Add request queuing system

## Common Issues

1. **Scryfall Database**: First run downloads ~100MB bulk data. If missing, run `python backend/scripts/download_scryfall.py`
2. **GPU Not Detected**: Ensure CUDA is properly installed for GPU acceleration
3. **Memory Usage**: EasyOCR loads 4 language models (~1.2GB). Consider reducing languages if memory-constrained
4. **Rate Limiting**: Default is 0.5s between requests per IP. Adjust in `main.py:_rate_limit()`
5. **CORS Errors**: Check that your domain is in the allowed origins list in `main.py`
6. **OCR Confidence Low**: Ensure images are high quality, well-lit, and properly oriented

## Code Style Notes

- Backend uses type hints throughout
- Frontend uses TypeScript with minimal inline styles
- All card names must be validated through Scryfall
- Error codes are defined in `error_taxonomy.py`
- Logging uses the telemetry module with trace IDs
- Follow existing patterns in codebase
- Comment in English for consistency