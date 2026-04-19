# 🎴 Screen2Deck - MTG Deck Scanner

[![CI/CD Pipeline](https://github.com/gbordes77/Screen2Deck/actions/workflows/ci.yml/badge.svg)](https://github.com/gbordes77/Screen2Deck/actions)
[![E2E Tests](https://github.com/gbordes77/Screen2Deck/actions/workflows/e2e-tests.yml/badge.svg)](https://github.com/gbordes77/Screen2Deck/actions/workflows/e2e-tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?logo=docker&logoColor=white)](https://hub.docker.com/r/screen2deck)

Transform screenshots of Magic: The Gathering decks into importable deck lists for MTGA, Moxfield, Archidekt, and more!

## 🚀 Status: Production Ready (v2.4.0)

Online OCR system with Scryfall API integration for card validation. v2.4.0 runs **EasyOCR + OpenCV preprocessing as the primary path** and keeps the Vision LLM chain (Gemini 2.5 Flash → Claude Haiku 4.5) as an **opt-in backup** that only fires when EasyOCR confidence drops below `OCR_MIN_CONF`. Scryfall resolution is batched via `/cards/collection`.

> 🙅 **Why OCR-first?** The MTG community asked for a deterministic, non-AI image recognition path they can trust. By default Screen2Deck never calls a multimodal LLM — upload a clean screenshot and the decklist comes back from classical computer vision alone.

```bash
# Quick Start - Online Mode
make test-online    # Run E2E tests in online mode
make up             # Start all services
```

Features:
- 🌐 **Always Online**: Direct integration with Scryfall API
- 🔍 **OCR-primary by default**: EasyOCR + OpenCV (CLAHE, denoise, adaptive threshold, super-res, 4-variant best-of) — no AI call on clean scans
- 🧯 **AI only as backup**: Low-confidence scans (<`OCR_MIN_CONF`) optionally fall back to Gemini/Claude; disabled entirely if no API key is set
- 📥 **Dynamic Models**: EasyOCR downloads models on demand (~64MB) on first run
- ⚡ **Real-time Updates**: Always current card database
- 🚀 **Simplified Deployment**: No pre-baking or offline setup needed
- ✅ **Validated**: Comprehensive online testing suite

## ✨ Features

### Core Functionality
- **🔍 Deterministic OCR primary path**: EasyOCR (beam-friendly thresholds tuned per [context7 docs](https://context7.com/jaidedai/easyocr)) over 4 OpenCV preprocessing variants — CLAHE contrast lift, unsharp-mask + non-local-means denoising, adaptive-threshold binarization, and optional 4× super-resolution for small crops
- **🧯 Vision LLM as optional backup**: Gemini 2.5 Flash → Claude Haiku 4.5, gated by `ENABLE_VISION_FALLBACK` and only invoked when EasyOCR's mean confidence drops below `OCR_MIN_CONF` ([vision fallback policy](./docs/VISION_FALLBACK_POLICY.md))
- **📦 Scryfall batch resolution**: `/cards/collection` endpoint (75 cards per request), User-Agent header, async-wrapped client — 60-card decks resolve in ~500 ms instead of ~7 s
- **🔍 Smart Matching**: Scryfall API validation (85-94% accuracy baseline, ≥85% target)
- **📤 Multi-Format Export**: MTGA, Moxfield, Archidekt, TappedOut, JSON
- **🤖 Discord Bot**: Full parity with web interface ([slash commands](./discord/README.md))
- **🔐 Security hardened**: JWT via PyJWT (CVE-2024-33663/33664 fixed), IDOR ownership check on `/api/ocr/status`, authenticated `/api/auth/api-key`, default-credential CI guard, CORS & rate limiting
- **♻️ Idempotency**: Image hash-based deduplication
- **⚡ Real-time Updates**: WebSocket support for live progress
- **🌐 Cloud-Native**: Optimized for online deployment

### Performance targets (see [DISCLAIMER.md](./DISCLAIMER.md) for measured vs projected)
- **~4.1s** projected P95 latency on the default EasyOCR path (pending a fresh `make bench-day0` run on v2.4.0)
- **~2.7s** projected P95 latency when operators opt into `VISION_PRIMARY=true` (Gemini structured output)
- **85-94%** OCR accuracy baseline on EasyOCR + Scryfall fuzzy match; +3-5 points qualitative on the opt-in Vision path (projected)
- **100+** concurrent users supported in load tests
- **50-80%** cache hit rate after warm-up
- **<500MB** memory usage per instance
- **20 req/min/IP** rate limiting on exports

### Enterprise Ready
- **🐳 Docker**: Production-hardened containers with non-root users
- **☸️ Kubernetes**: Full K8s manifests with HPA and monitoring
- **📊 Observability**: Prometheus metrics + OpenTelemetry tracing
- **🔄 CI/CD**: GitHub Actions with automated testing
- **🛡️ Security**: Complete auth system, validation, security headers
- **💾 Persistence**: PostgreSQL + Redis with job storage

## 🎯 Validation & Testing

```bash
# Run complete validation suite
./scripts/gate_final.sh

# Individual test components
make test          # Unit + integration tests
make bench-day0    # Performance benchmarks
make golden        # Export format validation
make parity        # Web/Discord consistency check
```

## 📋 Prerequisites

- Docker & Docker Compose (recommended)
- OR Python 3.11+ and Node.js 18+
- Redis (for job storage)
- PostgreSQL (optional, for user management)
Note: This project uses EasyOCR exclusively for OCR processing.

## 🏗️ Architecture (v2.4.0 - ONLINE-ONLY, OCR-primary)

```
┌─────────────────────────────────────────────────────────────┐
│                    Screen2Deck v2.4.0                       │
│       100% ONLINE · OCR-primary · AI is opt-in backup       │
└─────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│   Frontend   │────▶│   Backend    │────▶│  External APIs   │
│  (Next.js)   │     │  (FastAPI)   │     │                  │
│  Port: 3000  │     │  Port: 8080  │     │ • Scryfall API   │
└──────────────┘     └──────────────┘     │ • (opt-in) Gemini│
                            │              │ • (opt-in) Claude│
                            │              └──────────────────┘
                            │                       │
                            ▼                       │
                     ┌──────────────┐              │
                     │    Redis     │              │
                     │  Port: 6379  │              │
                     └──────────────┘              │
                            │                       │
                            ▼                       ▼
                     ┌──────────────┐     ┌──────────────────┐
                     │  PostgreSQL  │     │   EasyOCR Models │
                     │  Port: 5433  │     │  (Downloaded)    │
                     └──────────────┘     │    ~64MB         │
                                          └──────────────────┘

Data Flow (default — VISION_PRIMARY=false):
1. Upload Image → Frontend → Backend
2. OpenCV preprocessing → 4 variants (original, CLAHE, denoised+sharpen, adaptive threshold;
   4× super-res first when width < SUPERRES_MIN_WIDTH)
3. EasyOCR best-of pass over the 4 variants (early-stop at OCR_EARLY_STOP_CONF)
4. If mean confidence < OCR_MIN_CONF AND ENABLE_VISION_FALLBACK=true:
   retry with Vision LLM chain (Gemini 2.5 Flash → Claude Haiku 4.5).
   If no API key is configured, this step is a no-op and EasyOCR's
   best-effort result is returned as-is.
5. Regex parse deck sections → batch-validate via Scryfall /cards/collection
6. MTGO 60+15 redistribution + Scryfall fuzzy fill-in
7. Cache results in Redis (image-hash idempotency) → return formatted deck
```

## 🏃 Quick Start

### Option 1: Docker Environment (Recommended)

```bash
# Clone the repository
git clone https://github.com/gbordes77/Screen2Deck.git
cd Screen2Deck

# Start all services (ONLINE mode)
make up

# First run downloads EasyOCR models (~64MB)
# This happens automatically on first OCR request

# Run online E2E test
make test-online

# Run complete proof suite
make test          # Unit + integration tests
make golden        # Validate export formats
make parity        # Check Web/Discord parity

# Check health and metrics
make health
make metrics
```

### Using Docker Directly

```bash
# Configure environment
cp .env.example .env.production
nano .env.production  # Or use make generate-secrets

# Start all services
docker-compose up -d

# With GPU support
docker-compose -f docker-compose.gpu.yml up -d

# Production deployment
docker-compose -f docker-compose.prod.yml up -d
```

### Option 2: Local Development

```bash
# Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Note: EasyOCR models will be downloaded on first use (~64MB)
# Models are cached in ~/.EasyOCR/

# Start Redis
redis-server

# Run application
python -m app.main

# Frontend setup (in new terminal)
cd webapp
npm install
npm run dev
```

## 🔐 Security Configuration

### Required Environment Variables

```env
# Security (MUST CHANGE!)
JWT_SECRET_KEY=<generate-secure-32-char-key>
JWT_ALGORITHM=HS256

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/screen2deck

# Redis
REDIS_URL=redis://localhost:6379/0

# CORS (update for your domain)
CORS_ORIGINS=["http://localhost:3000","https://yourdomain.com"]

# OCR Configuration (primary path — EasyOCR + OpenCV)
OCR_MIN_CONF=0.62           # Below this, low-confidence fallback kicks in
OCR_EARLY_STOP_CONF=0.85    # Stop iterating variants once a run scores this
OCR_MIN_SPAN_CONF=0.3       # Drop OCR spans below this confidence
OCR_MIN_LINES=10            # Minimum qty-line count for a valid scan
ALWAYS_VERIFY_SCRYFALL=true # Mandatory Scryfall validation

# Super-Resolution (triggered on small screenshots)
ENABLE_SUPERRES=true        # Enable 4× super-resolution on thumbnails
SUPERRES_MIN_WIDTH=1200     # Trigger super-res below this width

# Vision LLM (opt-in backup — only fires when OCR confidence is too low
# AND ENABLE_VISION_FALLBACK=true AND an API key is set)
ENABLE_VISION_FALLBACK=true        # Enable the Vision LLM chain as a backup
VISION_PRIMARY=false               # Leave false to keep OCR as the primary path
VISION_PROVIDER=gemini,claude      # Chain order — first available wins
GEMINI_API_KEY=                    # Optional — free tier: https://aistudio.google.com/app/apikey
GEMINI_MODEL=gemini-2.5-flash
ANTHROPIC_API_KEY=                 # Optional — API access is separate from Claude Pro/Max
ANTHROPIC_MODEL=claude-haiku-4-5
```

### Generate Secure JWT Secret

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 📚 API Documentation

Full API documentation available at:
- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc
- **[API Reference](./docs/API.md)**: Detailed endpoint documentation

### Rate Limits
- **Export endpoints** (`/api/export/*`): 20 requests/minute per IP
- **OCR endpoints** (`/api/ocr/*`): 60 requests/minute per IP
- **Auth endpoints** (`/api/auth/*`): 10 requests/minute per IP

### Quick Example

```bash
# 1. Register user
curl -X POST http://localhost:8080/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","email":"demo@example.com","password":"demo123"}'

# 2. Login
TOKEN=$(curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password&username=demo&password=demo123" \
  | jq -r '.access_token')

# 3. Upload image
JOB_ID=$(curl -X POST http://localhost:8080/api/ocr/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@deck_image.jpg" \
  | jq -r '.jobId')

# 4. Get results
curl http://localhost:8080/api/ocr/status/$JOB_ID \
  -H "Authorization: Bearer $TOKEN"
```

## 🐳 Docker Deployment

```bash
# Build images
docker-compose -f docker-compose.prod.yml build

# Start services
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose logs -f backend

# Stop services
docker-compose down
```

## ☸️ Kubernetes Deployment

```bash
# Create namespace
kubectl create namespace screen2deck

# Apply configurations
kubectl apply -f k8s/ -n screen2deck

# Check status
kubectl get pods -n screen2deck

# Access service
kubectl port-forward svc/webapp 3000:3000 -n screen2deck
```

See [Deployment Guide](./docs/DEPLOYMENT.md) for detailed instructions.

## 📊 Monitoring

### Health Endpoints
- `/health` - Basic health check
- `/health/ready` - Readiness probe
- `/health/detailed` - Detailed system metrics

### Prometheus Metrics
- `/metrics` - Prometheus-compatible metrics endpoint

Available metrics:
- `screen2deck_ocr_requests_total`
- `screen2deck_ocr_duration_seconds`
- `screen2deck_cache_hits_total`
- `screen2deck_active_jobs`
- `screen2deck_errors_total`

## 🧪 Testing

### Run Tests

```bash
# Complete test suite with proofs
make test          # Unit + integration tests
make bench-day0    # Run benchmarks
make golden        # Validate export formats ([Golden Exports](./golden_exports/))
make parity        # Web/Discord parity check ([CI Job](.github/workflows/parity-test.yml))

# Individual test categories
pytest tests/unit -v           # Unit tests (business rules + exporters + anti-Tesseract)
# Note: tests/integration/ and tests/e2e/ were removed in v2.4.0 (PR #2,
# test honesty pass). Playwright e2e lives in tests/web-e2e/ and runs via
# `make e2e-ui` or `make e2e-smoke`.

# Run specific proof tools
python3 tools/bench_runner.py --images validation_set/images --truth validation_set/truth --out artifacts/reports/day0
python3 tools/golden_check.py --out artifacts/golden
python3 tools/parity_check.py --out artifacts/parity
```

### Test Coverage
- **Unit Tests**: Core business logic + MTG edge cases (DFC, Split, Adventure)
- **Integration Tests**: API endpoints and pipeline
- **E2E Tests**: Full OCR workflow with benchmarks
- **Golden Tests**: Export format validation (MTGA, Moxfield, Archidekt, TappedOut)
- **Parity Tests**: Web/Discord export consistency
- **Security Tests**: Anti-Tesseract guard (EasyOCR only)

### Key Components
- **FastAPI Backend**: High-performance async API (canonical entry: `backend/app/main.py`)
- **Redis**: Job storage, idempotency cache, rate-limit state
- **PostgreSQL**: User management (optional, required for authenticated job ownership)
- **Vision providers**: Gemini 2.5 Flash primary, Claude Haiku 4.5 fallback (both return typed JSON)
- **EasyOCR**: Fallback OCR path when the Vision call fails
- **Scryfall**: Online card validation via `/cards/collection` batch endpoint, bulk-hydrated on startup

## 🔒 Security & Privacy

### Security Features
- ✅ **JWT Authentication** with refresh tokens
- ✅ **API Key Support** for programmatic access
- ✅ **Rate Limiting** per IP and user
- ✅ **Input Validation** with sanitization
- ✅ **Security Headers** (CSP, HSTS, etc.)
- ✅ **Image Validation** with magic bytes
- ✅ **SQL Injection Prevention**
- ✅ **XSS Protection**
- ✅ **CORS Configuration**
- ✅ **Non-root Docker Containers**
- ✅ **Anti-Tesseract Guard**: CI blocks any pytesseract usage (EasyOCR only)

### 🛡️ GDPR Compliance
- **Data Retention** ([Full Policy](./docs/GDPR_POLICY.md)):
  - Images: 24 hours (auto-deleted)
  - Job metadata: 1 hour
  - Hash cache: 7 days
  - Logs: 7 days
  - Metrics: 30 days
- **Encryption**: At-rest (AES-256) and in-transit (TLS 1.3)
- **User Rights**: Export, deletion, opt-out APIs
- **No Tracking**: No analytics cookies or behavioral tracking

## 📈 Performance Metrics

See [DISCLAIMER.md](./DISCLAIMER.md) for the distinction between verified and projected metrics. Re-run `make smoke && make bench-day0` to produce fresh artifacts under `artifacts/reports/day0/`.

- **OCR Accuracy**: 85-94% fuzzy-match baseline on the validation set
- **Processing Time**: ~4.1s p95 projected on the default EasyOCR path, ~2.7s p95 when operators opt into `VISION_PRIMARY=true`
- **Throughput**: 100+ concurrent users supported in load tests
- **Cache Hit Rate**: 50-80% after warm-up (image-hash idempotency + Scryfall bulk)
- **Memory Usage**: <500MB per instance (steady state)
- **Startup Time**: bulk Scryfall hydrate adds ~2-5s to cold start

## 🆕 Advanced Features

### Idempotency & Deduplication
- **Deterministic Keys**: SHA256(image + pipeline version + config + scryfall snapshot)
- **Redis SETNX Locks**: Atomic lock acquisition prevents concurrent processing
- **TTL Alignment**: Cache expiry matches GDPR retention (24h images, 7d hashes)
- **Configuration-Aware**: Different results for different OCR settings

### Circuit Breaker for Vision API
- **Automatic Fallback Control**: Monitors fallback rate in 15-minute windows
- **Dynamic Threshold Adjustment**: Auto-increases thresholds when rate >15%
- **Resolution-Based Bands**: 
  - 720p: 55% confidence, 8 lines minimum
  - 1080p: 62% confidence, 10 lines minimum  
  - 1440p: 68% confidence, 12 lines minimum
  - 4K+: 72% confidence, 15 lines minimum
- **Cost Protection**: Circuit opens after 5 failures, recovers after 60s

### GDPR Compliance
- **Data Retention** (Redis TTLs driven by `DATA_RETENTION_*_HOURS/DAYS` env vars):
  - Images: 24 hours (configurable via `DATA_RETENTION_IMAGES_HOURS`)
  - Jobs: 1 hour (configurable via `DATA_RETENTION_JOBS_HOURS`)
  - Hashes: 7 days (configurable via `DATA_RETENTION_HASHES_DAYS`)
- **GDPR router**: `backend/app/routers/gdpr.py` is present but not yet wired into `main.py`. Treat GDPR endpoints as a documented extension point, not a supported surface, until [PLAN.md](./PLAN.md) lists the wiring as done.
- **Metrics**: Prometheus counters for GDPR operations live in `backend/app/core/metrics.py` (`gdpr_requests_total`, `retention_deleted_total`)

### Enterprise Security Hardening
- **Health Endpoint Protection**: IP allowlist for `/health/detailed`
- **Magic Number Validation**: Verifies actual file type vs extension
- **Discord Bot Security**: Token rotation, command permissions, rate limiting
- **Multi-Architecture Support**: linux/amd64 and linux/arm64 containers
- **SLO Monitoring**: Histogram metrics per processing stage

### Developer Tools
```bash
# Run comprehensive tests
make test

# Security scanning (includes anti-Tesseract check)
make security-scan

# Generate production secrets
make generate-secrets

# GDPR compliance testing
make gdpr-test
make gdpr-dry-run

# E2E benchmark with SLO validation
make e2e-day0  # Fails if SLOs not met

# Air-Gapped Demo Management
make demo-local       # Start offline demo
make validate-airgap  # Verify offline compliance
make pack-demo        # Create transportable package
make stop-local       # Stop demo services

# Example API calls
make example-upload
make example-export

# Health and metrics
make health
make metrics
```

## 🚀 Next Steps for New Team

### 🔐 Immediate Setup (Day 1)

1. **Navigate to Project**
   ```bash
   cd /Volumes/DataDisk/_Projects/Screen2Deck/backend
   ```

2. **Security Configuration**
   ```bash
   # Generate new JWT secret
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   # Update JWT_SECRET_KEY in .env file
   nano .env
   ```

3. **Database Setup**
   ```bash
   # Install and configure PostgreSQL (if not installed)
   brew install postgresql  # macOS
   brew services start postgresql
   createdb screen2deck
   
   # Install and start Redis (if not installed)
   brew install redis  # macOS
   brew services start redis
   ```

4. **Install Dependencies**
   ```bash
   # Already in backend directory
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

5. **Launch Application**
   ```bash
   python -m app.main
   # API will be available at http://localhost:8080
   # Check docs at http://localhost:8080/docs
   ```

### 📋 Week 1 Priorities

1. **Create Operational Runbook**
   - Document common procedures
   - Error resolution guides
   - Backup/restore processes
   - Incident response plans

2. **Deploy to Staging**
   - Set up staging environment
   - Configure CI/CD pipeline
   - Run integration tests
   - Validate all features

3. **Configure Monitoring**
   - Set up Grafana dashboards
   - Configure Prometheus alerts
   - Implement log aggregation
   - Set up uptime monitoring

4. **Load Testing**
   - Run Locust load tests
   - Benchmark performance
   - Identify bottlenecks
   - Optimize as needed

### 🎯 Production Deployment Checklist

- [ ] All secrets changed from defaults
- [ ] SSL/TLS certificates configured
- [ ] Database backups configured
- [ ] Redis persistence enabled
- [ ] Monitoring dashboards live
- [ ] Alerting rules configured
- [ ] Load testing completed
- [ ] Security scan passed
- [ ] Documentation reviewed
- [ ] Team trained on operations

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) first.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **EasyOCR** for the OCR engine
- **Scryfall** for the card database
- **FastAPI** for the backend framework
- **Next.js** for the frontend framework
- Magic: The Gathering is a trademark of Wizards of the Coast

## 📬 Support

- **GitHub Issues**: [Report bugs or request features](https://github.com/gbordes77/Screen2Deck/issues)
- **Documentation**: [Full documentation](./docs/)
- **API Reference**: [API documentation](./docs/API.md)
- **Deployment Guide**: [Deployment instructions](./docs/DEPLOYMENT.md)

---

**Built with ❤️ for the MTG community**