# Screen2Deck Makefile
# Production-ready operations and testing

.PHONY: help
help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Development
.PHONY: dev
dev: ## Start development environment
	docker-compose up -d
	@echo "Development environment started:"
	@echo "  Frontend: http://localhost:3000"
	@echo "  Backend:  http://localhost:8080"
	@echo "  API Docs: http://localhost:8080/docs"

.PHONY: stop
stop: ## Stop all services
	docker-compose down

.PHONY: clean
clean: stop ## Clean up containers and volumes
	docker-compose down -v
	rm -rf backend/app/data/*.json
	rm -rf backend/app/data/*.sqlite

# Testing
.PHONY: test
test: ## Run all tests
	cd backend && pytest tests/ -v --cov=app
	cd webapp && npm test
	cd discord && npm test

.PHONY: e2e-day0
e2e-day0: ## Run Day-0 E2E benchmark
	@echo "Running E2E benchmark..."
	@python backend/tools/bench/run.py --images ./validation_set --report ./reports/day0
	@echo ""
	@echo "Results:"
	@grep "Accuracy" reports/day0/benchmark_day0.md | head -1
	@grep "P95 Latency" reports/day0/benchmark_day0.md | head -1
	@echo ""
	@if grep -q "✅ PASS" reports/day0/benchmark_day0.md; then \
		echo "✅ All SLOs met!"; \
		exit 0; \
	else \
		echo "❌ SLO violations detected"; \
		exit 1; \
	fi

.PHONY: load-test
load-test: ## Run load test with Locust
	cd tests/load && locust -f load_test.py --host=http://localhost:8080 --users 100 --spawn-rate 10

# Docker operations
.PHONY: build
build: ## Build Docker images
	docker-compose build

.PHONY: build-multiarch
build-multiarch: ## Build multi-arch Docker images
	docker buildx build \
		--platform linux/amd64,linux/arm64 \
		--tag ghcr.io/gbordes77/screen2deck-backend:latest \
		--tag ghcr.io/gbordes77/screen2deck-backend:$(VERSION) \
		--build-arg VERSION=$(VERSION) \
		--build-arg BUILD_DATE=$(shell date -u +"%Y-%m-%dT%H:%M:%SZ") \
		--build-arg VCS_REF=$(shell git rev-parse --short HEAD) \
		--push \
		backend/

.PHONY: push
push: ## Push Docker images to registry
	docker-compose push

# Production
.PHONY: prod
prod: ## Start production environment
	docker-compose -f docker-compose.prod.yml up -d

.PHONY: prod-gpu
prod-gpu: ## Start production with GPU support
	docker-compose -f docker-compose.gpu.yml up -d

# Security
.PHONY: security-scan
security-scan: ## Run security scans
	@echo "Running Trivy scan..."
	@docker run --rm -v $(PWD):/src aquasec/trivy fs /src
	@echo ""
	@echo "Checking for Tesseract..."
	@if grep -r "tesseract\|pytesseract" backend/ --include="*.py"; then \
		echo "❌ TESSERACT FOUND! This is not allowed."; \
		exit 1; \
	else \
		echo "✅ No Tesseract found"; \
	fi

.PHONY: generate-secrets
generate-secrets: ## Generate secure secrets for production
	@echo "Generating secure secrets..."
	@echo "JWT_SECRET_KEY=$$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
	@echo "DATABASE_PASSWORD=$$(python -c 'import secrets; print(secrets.token_urlsafe(24))')"
	@echo "REDIS_PASSWORD=$$(python -c 'import secrets; print(secrets.token_urlsafe(24))')"

# GDPR compliance
.PHONY: gdpr-test
gdpr-test: ## Test GDPR data retention
	@echo "Testing GDPR retention..."
	@python backend/tests/test_retention.py
	@echo "✅ GDPR tests passed"

.PHONY: gdpr-dry-run
gdpr-dry-run: ## Dry run of data retention cleanup
	@python -c "from backend.app.core.retention import cleanup_expired_images; cleanup_expired_images(dry_run=True)"

# Monitoring
.PHONY: metrics
metrics: ## Show current metrics
	@curl -s http://localhost:9090/metrics | grep screen2deck | head -20

.PHONY: health
health: ## Check health status
	@echo "Basic health:"
	@curl -s http://localhost:8080/health | jq .
	@echo ""
	@echo "Detailed health (if authorized):"
	@curl -s http://localhost:8080/health/detailed | jq . || echo "Access denied (expected in production)"

# Release
.PHONY: release
release: ## Create a new release
	@echo "Current version: $(VERSION)"
	@echo "Creating release..."
	@git tag -a v$(VERSION) -m "Release v$(VERSION)"
	@git push origin v$(VERSION)
	@echo "✅ Release v$(VERSION) created"

.PHONY: changelog
changelog: ## Update changelog
	@echo "Updating CHANGELOG.md..."
	@echo "Add your changes manually to CHANGELOG.md"
	@echo "Then commit with: git commit -am 'docs: update changelog for v$(VERSION)'"

# Examples
.PHONY: example-upload
example-upload: ## Example: Upload image via curl
	@echo "Uploading test image..."
	@echo ""
	@echo "curl -X POST http://localhost:8080/api/ocr/upload \\"
	@echo "  -H 'Content-Type: multipart/form-data' \\"
	@echo "  -F 'file=@validation_set/test_deck_1.jpg'"
	@echo ""
	@echo "This returns a jobId. Then check status with:"
	@echo "curl http://localhost:8080/api/ocr/status/{jobId}"

.PHONY: example-export
example-export: ## Example: Export deck to MTGA format
	@echo "Example export request:"
	@echo ""
	@echo "curl -X POST http://localhost:8080/api/export/mtga \\"
	@echo "  -H 'Content-Type: application/json' \\"
	@echo "  -d '{"
	@echo '    "mainboard": ['
	@echo '      {"qty": 4, "name": "Lightning Bolt"},'
	@echo '      {"qty": 24, "name": "Mountain"}'
	@echo '    ],'
	@echo '    "sideboard": []'
	@echo "  }'"

# Variables
VERSION ?= 2.0.0
DOCKER_REGISTRY ?= ghcr.io/gbordes77

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m # No Color

# Default target
.DEFAULT_GOAL := help