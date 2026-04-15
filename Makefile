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

.PHONY: test-online
test-online: ## Run E2E test 100% ONLINE
	@node tests/webapp.online.js

.PHONY: smoke
smoke: ## End-to-end smoke test (boot stack, upload image, verify result, test export)
	@bash tests/smoke_test.sh

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
test: unit ## Run all Python unit tests (the only Python tests that still exist post-v2.4.0)

.PHONY: unit
unit: ## Run unit tests (tests/unit/ only — integration/ and e2e/ were removed in v2.4.0)
	@. .venv/bin/activate 2>/dev/null || python3 -m venv .venv && . .venv/bin/activate && pytest tests/unit $(PYTEST_ARGS)

.PHONY: integration
integration: ## (removed in v2.4.0) Use `make smoke` or `make e2e-smoke` instead
	@echo "tests/integration/ was removed in the v2.4.0 test-honesty pass."
	@echo "Replacements:"
	@echo "  - make smoke       → bash end-to-end smoke test"
	@echo "  - make e2e-smoke   → Playwright happy-path"
	@echo "  - make exports-goldens → HTTP golden diff against a live API"
	@exit 2

.PHONY: e2e
e2e: e2e-ui ## Alias for e2e-ui (Playwright). Python tests/e2e/ was removed in v2.4.0.

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

.PHONY: bench-truth
bench-truth: artifacts ## Run independent benchmark for truth metrics
	@echo "🔍 Running independent benchmark..."
	@. .venv/bin/activate 2>/dev/null || python3 -m venv .venv && . .venv/bin/activate && \
		pip install -q requests && \
		python tools/benchmark_independent.py \
			--images ./validation_set \
			--output ./reports/truth_bench.json \
			--url http://localhost:8080
	@echo "✅ Truth benchmark saved to reports/truth_bench.json"

.PHONY: bench-compare
bench-compare: ## Compare official vs truth benchmarks
	@echo "📊 Comparing benchmarks..."
	@echo "=== Official Benchmark (day0) ==="
	@cat reports/day0/benchmark_day0.json 2>/dev/null | jq -r '.accuracy' || echo "Not found"
	@echo ""
	@echo "=== Truth Benchmark (independent) ==="
	@cat reports/truth_bench.json 2>/dev/null | jq -r '.accuracy.exact_match.mean' || echo "Not found"
	@echo ""
	@echo "=== Differences ==="
	@diff -u <(cat reports/day0/benchmark_day0.json 2>/dev/null | jq '.') \
		<(cat reports/truth_bench.json 2>/dev/null | jq '.') || true

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
	@# POSTGRES_PASSWORD defaults to a non-default string so the secrets-scan
	@# CI guard (security-checks.yml) stays green. Override via env var for
	@# reproducibility across runs: `POSTGRES_PASSWORD=... make ci-health`.
	@PW="$${POSTGRES_PASSWORD:-ci-$$(date +%s)-s2d}"; \
	echo "JWT_SECRET_KEY=$${JWT_SECRET_KEY:-ci-test-secret-at-least-32-bytes-long}" > backend/.env.docker; \
	printf 'DATABASE_URL=postgresql+psycopg://s2d_ci:%s@postgres:5432/s2d\nREDIS_URL=redis://redis:6379/0\nOCR_MIN_CONF=0.62\nALWAYS_VERIFY_SCRYFALL=true\nFEATURE_TELEMETRY=false\nOTEL_SDK_DISABLED=true\n' "$$PW" >> backend/.env.docker
	@docker compose --profile core up -d --build redis postgres backend
	@for i in {1..40}; do curl -sf http://localhost:8080/health && echo " ✅ Health check passed!" && exit 0; sleep 3; done; echo " ❌ Health check failed!" && exit 1

.PHONY: status
status: ## Show service status
	@docker compose ps

# Local Demo Hub commands
.PHONY: docs-build
docs-build: ## Build MkDocs static documentation
	@echo "📚 Building documentation..."
	@docker compose -f docker-compose.local.yml run --rm docs
	@echo "✅ Docs built in _build/docs/"

.PHONY: web-build
web-build: ## Build Next.js static web app
	@echo "🎨 Building web UI..."
	@docker compose -f docker-compose.local.yml run --rm web
	@echo "✅ Web UI built in _build/web/"

.PHONY: demo-local
demo-local: ## Launch local demo hub (app/api/docs/nginx) on http://localhost:8088
	@echo "🚀 Starting local demo hub..."
	@mkdir -p _build/web _build/docs artifacts playwright-report webapp/public/demo data
	# Build statiques avant Nginx
	@$(MAKE) web-build
	@$(MAKE) docs-build
	# Lancer API+Nginx (web/docs sont déjà produits sur disque)
	@docker compose -f docker-compose.local.yml up -d --build api nginx redis postgres
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
# ONLINE-ONLY - No offline database

# --- release + version discipline ------------------------------------------

.PHONY: bump-version
bump-version: ## Bump version in main.py, README, CLAUDE.md, CHANGELOG, package.json (usage: make bump-version VERSION=2.5.0)
	@if [ -z "$(VERSION)" ]; then \
		echo "Usage: make bump-version VERSION=x.y.z"; \
		exit 1; \
	fi
	@echo "Bumping version to $(VERSION)..."
	@python3 -c "\
import re, sys; \
v = '$(VERSION)'; \
assert re.match(r'^\d+\.\d+\.\d+$$', v), f'Invalid semver: {v}'; \
files = { \
    'backend/app/main.py': [r'version=\"\d+\.\d+\.\d+\"'], \
    'README.md': [r'Screen2Deck v\d+\.\d+\.\d+'], \
    'CLAUDE.md': [r'Production Ready \(v\d+\.\d+\.\d+\)'], \
    'webapp/package.json': [r'\"version\": \"\d+\.\d+\.\d+\"'], \
}; \
repl = { \
    'backend/app/main.py': [f'version=\"{v}\"'], \
    'README.md': [f'Screen2Deck v{v}'], \
    'CLAUDE.md': [f'Production Ready (v{v})'], \
    'webapp/package.json': [f'\"version\": \"{v}\"'], \
}; \
touched = 0; \
for f, pats in files.items(): \
    try: \
        with open(f) as fh: content = fh.read() \
    except FileNotFoundError: continue; \
    for pat, rep in zip(pats, repl[f]): \
        new = re.sub(pat, rep, content); \
        if new != content: content = new; touched += 1 \
    with open(f, 'w') as fh: fh.write(content) \
print(f'Touched {touched} version string(s). Run: git diff')"
	@echo "Done. Don't forget to update CHANGELOG.md by hand and commit."

.PHONY: doc-lint
doc-lint: ## Flag doc-to-code drift (stale v2.x mentions, version stamp mismatches)
	@echo "Scanning for version drift..."
	@STAMP=$$(grep -oE 'version="[0-9]+\.[0-9]+\.[0-9]+"' backend/app/main.py | head -1 | sed 's/version="//; s/"//') ; \
	echo "backend/app/main.py version=$$STAMP" ; \
	DOC_STAMP=$$(grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' README.md | head -1) ; \
	echo "README.md top stamp=$$DOC_STAMP" ; \
	if [ "v$$STAMP" != "$$DOC_STAMP" ] ; then \
	  echo "  ⚠ DRIFT: README.md and main.py disagree" ; \
	fi
	@echo ""
	@echo "Root .md files older than 30 days:"
	@find . -maxdepth 1 -name "*.md" -mtime +30 -print 2>/dev/null | sed 's/^/  /' || echo "  (none)"
	@echo ""
	@echo "Stale 'OpenAI' mentions (should be Gemini/Claude post-ADR 0001):"
	@grep -l -r --include="*.md" --exclude-dir=docs/adr 'OpenAI' . 2>/dev/null | sed 's/^/  /' || echo "  (none)"

.DEFAULT_GOAL := help
