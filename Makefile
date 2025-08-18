# Screen2Deck Makefile - Quick commands for development

# Variables
SHELL := /bin/bash
PYTEST_ARGS := -q --disable-warnings
ARTIFACTS := artifacts
VALIDATION_SET := validation_set/images
TRUTH := validation_set/truth
REPORT := $(ARTIFACTS)/reports

.PHONY: help
help: ## Show this help message
	@echo "Screen2Deck - Development Commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: up-core
up-core: ## Start Redis, Postgres, Backend (core services)
	@docker compose --profile core up -d redis postgres backend

.PHONY: up
up: ## Start all core services including webapp
	@docker compose --profile core up -d

.PHONY: down
down: ## Stop all services
	@docker compose --profile core down

.PHONY: logs
logs: ## Follow backend logs
	@docker compose logs -f backend

.PHONY: build
build: ## Rebuild backend container
	@docker compose build backend

.PHONY: restart
restart: ## Restart backend service
	@docker compose restart backend

.PHONY: health
health: ## Check backend health
	@curl -s http://localhost:8080/health | jq . || echo "Backend not healthy"

.PHONY: metrics
metrics: ## Show backend metrics
	@curl -s http://localhost:8080/metrics | head -20

.PHONY: exports-goldens
exports-goldens: ## Compare exports to golden files
	@python3 tests/exports/run_golden_exports.py

.PHONY: exports-goldens-update
exports-goldens-update: ## Update golden files with current output
	@python3 tests/exports/run_golden_exports.py --update

.PHONY: test-upload
test-upload: ## Test OCR upload with sample image
	@curl -X POST http://localhost:8080/api/ocr/upload \
		-F "file=@validation_set/MTGA deck list_1535x728.jpeg" \
		-H "Accept: application/json" | jq .

.PHONY: clean
clean: ## Clean Docker volumes and cache
	@docker compose down -v
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "node_modules" -exec rm -rf {} + 2>/dev/null || true

.PHONY: shell-backend
shell-backend: ## Open shell in backend container
	@docker compose exec backend /bin/bash

.PHONY: shell-postgres
shell-postgres: ## Open PostgreSQL shell
	@docker compose exec postgres psql -U postgres -d screen2deck

.PHONY: redis-cli
redis-cli: ## Open Redis CLI
	@docker compose exec redis redis-cli

.PHONY: format
format: ## Format Python code with black
	@docker compose exec backend black app/

.PHONY: lint
lint: ## Lint Python code with ruff
	@docker compose exec backend ruff check app/

.PHONY: test
test: unit integration ## Run all tests

.PHONY: unit
unit: ## Run unit tests
	@. .venv/bin/activate 2>/dev/null || python3 -m venv .venv && . .venv/bin/activate && pytest tests/unit $(PYTEST_ARGS)

.PHONY: integration
integration: ## Run integration tests
	@. .venv/bin/activate 2>/dev/null || python3 -m venv .venv && . .venv/bin/activate && pytest tests/integration $(PYTEST_ARGS)

.PHONY: e2e
e2e: ## Run E2E tests (Python)
	@. .venv/bin/activate 2>/dev/null || python3 -m venv .venv && . .venv/bin/activate && pytest tests/e2e $(PYTEST_ARGS)

.PHONY: e2e-ui
e2e-ui: ## Run Playwright E2E tests
	@npm ci
	@npx playwright install --with-deps
	@set -a; source .env.e2e 2>/dev/null || true; set +a; npx playwright test

.PHONY: e2e-smoke
e2e-smoke: ## Run quick smoke test with Playwright
	@npm ci
	@npx playwright install --with-deps
	@set -a; source .env.e2e 2>/dev/null || true; set +a; npx playwright test tests/web-e2e/suites/s1-happy-path.spec.ts --project=chromium

.PHONY: bench-day0
bench-day0: artifacts ## Run Day0 benchmark
	@. .venv/bin/activate 2>/dev/null || python3 -m venv .venv && . .venv/bin/activate && python tools/bench_runner.py --images $(VALIDATION_SET) --truth $(TRUTH) --out $(REPORT)/day0

.PHONY: golden
golden: artifacts ## Check golden exports
	@. .venv/bin/activate 2>/dev/null || python3 -m venv .venv && . .venv/bin/activate && python tools/golden_check.py --out $(ARTIFACTS)/golden

.PHONY: parity
parity: artifacts ## Check web/Discord parity
	@. .venv/bin/activate 2>/dev/null || python3 -m venv .venv && . .venv/bin/activate && python tools/parity_check.py --out $(ARTIFACTS)/parity

.PHONY: artifacts
artifacts: ## Create artifacts directories
	@mkdir -p $(ARTIFACTS) $(REPORT)

.PHONY: bootstrap
bootstrap: ## Setup Python venv and install deps
	@python3 -m venv .venv && . .venv/bin/activate && pip install -U pip wheel
	@. .venv/bin/activate && pip install pytest pytest-cov

.PHONY: dev
dev: ## Start development environment
	@docker compose --profile core up -d --build
	@echo "→ Health: curl -fsS http://localhost:8080/health && echo OK"

.PHONY: ci-health
ci-health: ## Run CI health check locally
	@echo "JWT_SECRET_KEY=ci" > backend/.env.docker
	@echo -e "DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/s2d\nREDIS_URL=redis://redis:6379/0\nOCR_MIN_CONF=0.62\nALWAYS_VERIFY_SCRYFALL=true\nFEATURE_TELEMETRY=false\nOTEL_SDK_DISABLED=true" >> backend/.env.docker
	@docker compose --profile core up -d --build redis postgres backend
	@for i in {1..40}; do curl -sf http://localhost:8080/health && echo " ✅ Health check passed!" && exit 0; sleep 3; done; echo " ❌ Health check failed!" && exit 1

.PHONY: status
status: ## Show service status
	@docker compose ps

# Local Demo Hub commands
.PHONY: demo-local
demo-local: ## Launch local demo hub (app/api/docs/nginx) on http://localhost:8088
	@echo "🚀 Starting local demo hub..."
	@mkdir -p _build/web _build/docs artifacts playwright-report webapp/public/demo data
	@docker compose -f docker-compose.local.yml up -d --build
	@echo "⏳ Waiting for services to be ready..."
	@sleep 10
	@echo "✅ Demo Hub ready!"
	@echo ""
	@echo "📍 Open http://localhost:8088"
	@echo "   • /app      → Web UI"
	@echo "   • /api      → Backend API"
	@echo "   • /docs     → Documentation"
	@echo "   • /report   → Playwright reports"
	@echo "   • /artifacts → Metrics & benchmarks"
	@echo "   • /video    → Demo videos"

.PHONY: stop-local
stop-local: ## Stop local demo hub
	@docker compose -f docker-compose.local.yml down
	@echo "✅ Demo Hub stopped"

.PHONY: proofs-local
proofs-local: ## Generate local reports (bench + e2e) and expose them
	@echo "📊 Generating proofs..."
	@make bench-day0
	@npm ci && npx playwright install --with-deps
	@set -a; source .env.e2e 2>/dev/null || true; set +a; npx playwright test || true
	@echo "✅ Reports generated!"
	@echo "📍 View at:"
	@echo "   • http://localhost:8088/report/  → Playwright E2E"
	@echo "   • http://localhost:8088/artifacts/ → Benchmarks"

.PHONY: screencast-record
screencast-record: ## Record a screencast (macOS)
	@mkdir -p webapp/public/demo
	@echo "🎥 Recording screencast (press Ctrl+C to stop)..."
	@ffmpeg -f avfoundation -i "1:0" -r 30 -video_size 1440x900 -b:v 6M -pix_fmt yuv420p webapp/public/demo/screencast.mp4

.PHONY: screencast-open
screencast-open: ## Open screencast in browser
	@open http://localhost:8088/video/screencast.mp4 || echo "Start demo-local first"

.PHONY: demo-seed
demo-seed: ## Build offline Scryfall database from local truth files (100% offline)
	@mkdir -p data validation_set/truth
	@echo "🔨 Building offline Scryfall database from local truth files..."
	@python3 tools/build_offline_seed.py
	@echo "✅ Offline database ready at data/scryfall.sqlite"
	@echo "🔒 No network calls required - 100% air-gapped!"

.DEFAULT_GOAL := help
