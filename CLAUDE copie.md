# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ AVERTISSEMENT - 16 AOÛT 2025

**Claude Opus 4.1 est NUL pour ce projet**. Il a essayé de réparer l'OCR et a tout cassé :
- ❌ Le système qui fonctionnait ne marche plus
- ❌ EasyOCR détecte des fragments illisibles 
- ❌ 0 cartes détectées après des heures de travail
- ❌ Incompétent et inutile

**Le Chef/PO a raison** : Claude ne sait pas travailler sur ce projet.

## 🚨 CRITICAL OCR FLOW - NEVER MODIFY WITHOUT AUTHORIZATION 🚨

### ⚠️ MANDATORY OCR PROCESSING FLOW ⚠️
```
┌──────────────────────────────────────────────────────────────┐
│ 🔴 DO NOT BYPASS THIS FLOW - BREAKING IT CAUSES REGRESSIONS │
└──────────────────────────────────────────────────────────────┘

1. IMAGE UPLOAD
      ↓
2. 🐍 EASYOCR (PRIMARY ENGINE) ← MUST BE FIRST!
      ├─ Detects "Sideboard" keyword
      ├─ Separates mainboard/sideboard
      └─ Returns confidence score
      ↓
3. CONFIDENCE CHECK
      ├─ IF > 60% → Continue to Scryfall
      └─ IF < 60% → Use OpenAI as FALLBACK ONLY
      ↓
4. 🔍 SCRYFALL VALIDATION
      ├─ Fuzzy matching
      └─ Card correction
      ↓
5. RETURN RESULTS
      ├─ Mainboard: 60 cards
      └─ Sideboard: 15 cards
```

### ❌ NEVER DO THIS:
- Skip EasyOCR and go directly to OpenAI
- Set `useOpenAI = true` in ocrService.ts
- Bypass the confidence check
- Ignore sideboard detection

### ✅ ALWAYS DO THIS:
- EasyOCR runs FIRST (it detects sideboard)
- OpenAI is FALLBACK only (< 60% confidence)
- Preserve the is_sideboard flag from Python

## Project Overview

MTG Screen-to-Deck v2.1.0 - AI-powered Magic: The Gathering deck scanner for MTGA/MTGO screenshots (60 mainboard + 15 sideboard cards). 

**Current Status**: 🔧 In Development - Requires validation before production deployment  
**See**: `VALIDATION_WORKFLOW.md` for required validation steps

The project consists of three main components:
- **Web Application**: React/TypeScript frontend with Express backend, automatic clipboard copy
- **Discord Bot**: Python bot with EasyOCR, Scryfall integration, and clipboard service
- **API Server**: Node.js/Express server with enhanced OCR pipeline

## 📚 DOCUMENTATION RULES - IMPORTANT

### Documentation Structure & Standards
La documentation est **100% complète et organisée** dans `/DOCUMENTATION_FINALE/` avec:
- **0 doublon** - Chaque document a un rôle unique
- **0 contradiction** - Information cohérente partout
- **Score conformité**: 92/100 selon les bonnes pratiques

### Structure Obligatoire
```
DOCUMENTATION_FINALE/
├── 01_QUICK_START/      # Guides démarrage (USER_GUIDE, ADMIN_GUIDE)
├── 02_OCR_RULES/        # 6 règles OCR optimisées
├── 03_ARCHITECTURE/     # Specs techniques (API, Discord, Web)
├── 04_DEPLOYMENT/       # Guides déploiement
├── 05_DEVELOPMENT/      # Pour contributeurs
├── 06_HANDOVER/         # Passation projet
├── ARCHIVES_2025_07/    # Docs obsolètes avec warnings
└── Documents standards  # CHANGELOG, LICENSE, SECURITY, FAQ, etc.
```

### Règles Strictes
1. **NE JAMAIS créer de doublons** - Vérifier si le document existe avant création
2. **Toujours mettre à jour** plutôt que créer un nouveau document
3. **Utiliser CURRENT_STATE.md** comme source de vérité pour les métriques
4. **Ajouter warnings** sur les documents obsolètes dans ARCHIVES
5. **Maintenir la cohérence** - v2.1.0 partout

### Documents de Référence
- **Métriques actuelles**: `CURRENT_STATE.md`
- **Règles OCR**: `02_OCR_RULES/MASTER_OCR_RULES.md`
- **Guide utilisateur**: `01_QUICK_START/USER_GUIDE.md`
- **Guide admin**: `01_QUICK_START/ADMIN_GUIDE.md`
- **Tests**: `TESTING.md`
- **Glossaire**: `GLOSSARY.md`

## Common Development Commands

### Full Stack Development
```bash
# Install all dependencies (frontend + backend)
npm install

# Run both frontend and backend in development mode
npm run dev

# Run for self-hosting (exposes on LAN)
npm run dev:selfhost

# Build production version
npm run build

# Run tests
npm run test

# Lint code
npm run lint
npm run lint:fix

# Type check TypeScript
cd client && npm run type-check
```

### Backend Server Commands
```bash
cd server
npm run dev        # Development mode with hot reload
npm run build      # Build TypeScript to JavaScript
npm run start      # Start production server
npm run test       # Run Jest tests
npm run lint       # ESLint check
```

### Frontend Client Commands
```bash
cd client
npm run dev        # Start Vite dev server (port 5173)
npm run build      # Build for production
npm run preview    # Preview production build
npm run lint       # ESLint check
```

### Discord Bot Commands
```bash
cd discord-bot
pip install -r requirements.txt  # Install Python dependencies
python bot.py                     # Run bot
./start_bot.sh                   # Automated startup script

# Testing
python tests/test_parser.py      # Test OCR parser
python tests/test_scryfall.py    # Test Scryfall integration
python tests/test_export.py      # Test export formats
```

### Docker Commands
```bash
docker-compose up -d              # Start all services
docker-compose -f docker-compose.prod.yml up -d  # Production deployment
docker-compose logs -f            # View logs
docker-compose down              # Stop services
```

## Architecture Overview

### Technology Stack
- **Frontend**: React 18, TypeScript, Vite, TailwindCSS, React Router
- **Backend**: Node.js, Express, TypeScript, OpenAI Vision API
- **Discord Bot**: Python 3.8+, discord.py, EasyOCR, Scryfall API
- **External Services**: OpenAI Vision (OCR), Scryfall API (card validation), optional Redis cache, Cloudflare R2, Supabase

### Key API Endpoints
- `POST /api/ocr/upload` - Upload image for OCR processing (returns processId)
- `GET /api/ocr/status/:processId` - Check OCR processing status
- `GET /api/cards/search` - Search Scryfall for cards
- `POST /api/cards/validate` - Validate card names
- `POST /api/export/:format` - Export deck to specific format (MTGA, Moxfield, etc.)
- `POST /api/export/all` - Export deck to all formats

### Data Flow
1. User uploads image via web UI or Discord
2. Image processed by OpenAI Vision API (web) or EasyOCR (Discord bot)
3. Card names validated/corrected via Scryfall API with fuzzy matching
4. Results cached and returned with export options
5. Multiple export formats available (MTGA, Moxfield, Archidekt, TappedOut)

### Key Services
- **enhancedOcrServiceGuaranteed.ts**: Service OCR avec détection 60+15 cartes
- **optimizedOcrService.ts**: Parallel pipelines with super-resolution and zone detection
- **scryfallService.ts**: Smart caching with fuzzy matching
- **clipboardService.ts**: Auto-copy to clipboard on web and Discord
- **ocr_parser_easyocr.py**: Discord bot's OCR with MTGO land fix
- **mtgo_land_correction_rule.py**: Critical fix for systematic MTGO bug

### Environment Configuration
Required environment variables:
- `OPENAI_API_KEY` - Required for web OCR
- `DISCORD_TOKEN` - Required for Discord bot
- `API_BASE_URL` - Backend API URL (default: http://localhost:3001/api)
- `SCRYFALL_API_URL` - Scryfall API (default: https://api.scryfall.com)
- Optional: Redis, Cloudflare R2, Supabase credentials

### Testing & Validation

⚠️ **IMPORTANT**: No production claims should be made without completing the validation workflow.

- **Backend**: Jest tests (currently using mocks - MUST be replaced with real images)
- **Frontend**: Component tests with Vite
- **Discord Bot**: pytest with async support + clipboard tests
- **E2E Validation**: Pending implementation with real MTGA/MTGO screenshots
- **Performance**: Target < 5s per deck (to be validated)
- **Cache Hit Rate**: Target > 90% on repeated cards (to be measured)

**Required before production**:
1. Configure real API keys (OpenAI, Discord)
2. Run tests with actual screenshots (20+ images)
3. Measure and document real performance metrics
4. Complete all phases in `VALIDATION_WORKFLOW.md`

See `VALIDATION_WORKFLOW.md` for complete validation process.

### OCR Optimization Rules - Target Objectives
1. **MTGO Land Fix**: Automatic correction of systematic land count bug (critical)
2. **Super-Resolution**: 4x upscaling for images < 1200px width
3. **Zone Detection**: Adaptive zone extraction for mainboard/sideboard
4. **Smart Cache**: Fuzzy matching with Levenshtein, Jaro-Winkler, Phonetic algorithms
5. **Parallel Processing**: Optimized for HD images
6. **Iterative Refinement**: Targets 60+15 cards detection through multiple attempts
7. **Auto-Clipboard**: Deck automatically copied on successful OCR
- See `NOUVELLES_REGLES_OCR_100_POURCENT.md` for complete documentation

### Development Workflow
1. Frontend runs on port 5173, proxies `/api` calls to backend on port 3001
2. Backend validates env vars on startup via `validateEnv.ts`
3. Discord bot can run independently or connect to backend API
4. All components support hot reload in development mode
5. Use concurrent development with `npm run dev` for full stack
6. **IMPORTANT**: Follow `VALIDATION_WORKFLOW.md` before claiming production ready
7. Test with real images: `npm run test:e2e` (currently using mocks - needs update)
8. **Check documentation rules**: See DOCUMENTATION_FINALE/DOCUMENTATION_RULES.md before modifying docs

### Features
- **OCR Processing**: For MTGA/MTGO screenshots
- **Auto-Clipboard Copy**: Instant paste into MTG Arena
- **Multi-Format Export**: MTGA, Moxfield, Archidekt, TappedOut, JSON
- **Smart Caching**: With 30-minute TTL
- **Performance**: Target < 5s processing time
- **Discord Integration**: Slash commands, ephemeral messages, clipboard service