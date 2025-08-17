# Screen2Deck Makefile - Quick commands for development

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
test: ## Run backend tests
	@docker compose exec backend pytest

.PHONY: ci-health
ci-health: ## Run CI health check locally
	@echo "JWT_SECRET_KEY=ci" > backend/.env.docker
	@echo -e "DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/s2d\nREDIS_URL=redis://redis:6379/0\nOCR_MIN_CONF=0.62\nALWAYS_VERIFY_SCRYFALL=true\nFEATURE_TELEMETRY=false\nOTEL_SDK_DISABLED=true" >> backend/.env.docker
	@docker compose --profile core up -d --build redis postgres backend
	@for i in {1..40}; do curl -sf http://localhost:8080/health && echo " ✅ Health check passed!" && exit 0; sleep 3; done; echo " ❌ Health check failed!" && exit 1

.PHONY: status
status: ## Show service status
	@docker compose ps

.DEFAULT_GOAL := help
