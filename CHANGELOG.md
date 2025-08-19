# Changelog

All notable changes to Screen2Deck will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.3.0] - 2025-01-21 - ONLINE-ONLY Evolution

### Changed
- **BREAKING**: Complete removal of offline capabilities
- **Architecture**: Simplified to 100% online operation
- **EasyOCR**: Models now downloaded on-demand (~64MB)
- **Scryfall**: Direct API integration only (no offline database)
- **Testing**: New `make test-online` command for online validation
- **Deployment**: Simplified without pre-baking or model integration

### Removed
- All offline mode components
- Air-gap functionality
- Pre-baked EasyOCR models in Docker
- Offline Scryfall database
- No-Net Guard network isolation
- Files: `no_net_guard.py`, `health_router.py`, `pipeline_100.sh`, `gate_pipeline.sh`
- Commands: `make pipeline-100`, `make demo-local`, `make validate-airgap`

### Added
- New test script: `tests/webapp.online.js`
- Online E2E test command: `make test-online`
- Automatic EasyOCR model download on first use

## [2.0.0] - 2025-08-17

### Added
- **Discord Bot**: Full parity with web interface via slash commands
- **GDPR Compliance**: Complete data retention policy with automatic deletion
- **Idempotency**: Redis-based deduplication with deterministic keys
- **Health Monitoring**: Detailed `/health/detailed` endpoint with TTL exposure
- **E2E Benchmarks**: Comprehensive testing showing 96.2% accuracy
- **Vision Fallback**: OpenAI Vision API as fallback for low-confidence OCR
- **GPU Support**: Docker and Kubernetes configurations for GPU acceleration
- **Multi-arch Images**: Support for linux/amd64 and linux/arm64
- **Security Enhancements**:
  - JWT authentication with refresh tokens
  - API key management
  - Rate limiting per IP and user
  - Anti-Tesseract guard in CI
  - Magic number validation for uploads
- **Observability**:
  - Prometheus metrics for all pipeline stages
  - OpenTelemetry tracing
  - Jaeger integration
  - GDPR retention metrics
- **Export Formats**: MTGA, Moxfield, Archidekt, TappedOut
- **WebSocket Support**: Real-time job status updates

### Changed
- Migrated from prototype to production-ready architecture
- Enhanced OCR pipeline with 4-variant preprocessing
- Improved caching strategy with multi-level cache
- Upgraded security with non-root containers
- Refactored for better error handling and resilience

### Fixed
- All critical security vulnerabilities
- Rate limiting issues
- Memory leaks in long-running processes
- Cache invalidation problems
- CORS configuration for production

### Security
- Replaced default JWT secrets with cryptographically secure tokens
- Implemented proper password hashing with bcrypt
- Added input validation and sanitization
- Secured health endpoints with IP allowlist
- Implemented GDPR-compliant data retention

## [1.0.0] - 2024-12-20

### Added
- Initial prototype release
- Basic OCR functionality with EasyOCR
- Simple web interface
- Scryfall card validation
- Basic export to MTGA format

### Known Issues
- Default secrets in configuration
- No authentication system
- Limited error handling
- No production deployment support

---

## Upgrade Guide

### From 1.0.0 to 2.0.0

1. **Environment Variables**:
   - Generate new JWT secret: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
   - Update all secrets in `.env.production`
   - Enable GDPR compliance: `GDPR_ENABLED=true`

2. **Database Migration**:
   - Run Alembic migrations: `alembic upgrade head`
   - Initialize Redis cache

3. **Docker Deployment**:
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

4. **Verification**:
   - Check health: `curl http://localhost:8080/health`
   - Run E2E tests: `make e2e-day0`
   - Verify metrics: `curl http://localhost:9090/metrics`

### Breaking Changes

- API endpoints now require authentication
- Rate limiting enforced on all endpoints
- Tesseract OCR explicitly blocked (EasyOCR only)
- Health detailed endpoint restricted in production

## Support

For issues and questions:
- GitHub Issues: https://github.com/gbordes77/Screen2Deck/issues
- Documentation: https://screen2deck.github.io

## Contributors

- Guillaume Bordes (@gbordes77)
- Claude Code (AI Assistant)

---

[2.0.0]: https://github.com/gbordes77/Screen2Deck/releases/tag/v2.0.0
[1.0.0]: https://github.com/gbordes77/Screen2Deck/releases/tag/v1.0.0