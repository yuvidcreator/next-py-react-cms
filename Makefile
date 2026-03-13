# =============================================================================
# PyPress CMS — Makefile
# =============================================================================
# Developer CLI for PyPress. Every common operation is a single command.
#
# WordPress equivalent: WP-CLI (wp plugin install, wp db export, etc.)
# but for the entire Docker-orchestrated stack.
#
# Usage:
#   make dev          — Start development environment (hot reload)
#   make up           — Start production environment
#   make down         — Stop all services
#   make test         — Run test suite
#   make logs         — Follow all service logs
#   make help         — Show all available commands
# =============================================================================

.PHONY: help dev up down restart build logs test \
        shell-backend shell-db shell-redis \
        migrate migrate-create seed-demo \
        backup backup-list restore \
        ssl-setup ssl-renew validate-networks \
        health status clean \
        lint format type-check

# ── Default / Help ──────────────────────────────────────────────────────────
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo ""
	@echo "PyPress CMS — Available Commands"
	@echo "================================"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ── Environment Detection ───────────────────────────────────────────────────
# Check for .env file — refuse to start without it (just like WordPress
# redirects to the install wizard if wp-config.php is missing)
check-env:
	@if [ ! -f .env ]; then \
		echo ""; \
		echo "ERROR: .env file not found!"; \
		echo ""; \
		echo "PyPress needs a .env file to run (like WordPress needs wp-config.php)."; \
		echo "Create one from the template:"; \
		echo ""; \
		echo "  cp .env.example .env"; \
		echo "  # Then edit .env with your settings"; \
		echo ""; \
		exit 1; \
	fi

# ── Docker Compose Shorthands ───────────────────────────────────────────────
DC := docker compose
DC_DEV := $(DC) -f docker-compose.yml -f docker-compose.dev.yml
DC_TEST := $(DC) -f docker-compose.yml -f docker-compose.test.yml

# ── Lifecycle Commands ──────────────────────────────────────────────────────
dev: check-env ## Start development environment (hot reload, ports exposed)
	$(DC_DEV) up --build -d
	@echo ""
	@echo "PyPress development environment is running!"
	@echo ""
	@echo "  Frontend:  http://localhost:3000"
	@echo "  Admin:     http://localhost:3001"
	@echo "  Backend:   http://localhost:8000"
	@echo "  API Docs:  http://localhost:8000/api/docs"
	@echo "  Database:  localhost:5432"
	@echo "  Redis:     localhost:6379"
	@echo ""

up: check-env ## Start production environment
	$(DC) up --build -d
	@echo ""
	@echo "PyPress is running in production mode."
	@echo ""
	@echo "  Site:   http://localhost (or your configured domain)"
	@echo "  Admin:  http://localhost/admin"
	@echo ""

down: ## Stop all services
	$(DC_DEV) down 2>/dev/null; $(DC) down 2>/dev/null
	@echo "All PyPress services stopped."

restart: ## Restart all services (preserves volumes)
	$(DC) restart
	@echo "All services restarted."

build: ## Rebuild all Docker images (no cache)
	$(DC) build --no-cache
	@echo "All images rebuilt."

# ── Logging ─────────────────────────────────────────────────────────────────
logs: ## Follow all service logs (Ctrl+C to stop)
	$(DC) logs -f --tail=100

logs-backend: ## Follow backend logs only
	$(DC) logs -f --tail=100 backend

logs-frontend: ## Follow frontend logs only
	$(DC) logs -f --tail=100 frontend

logs-worker: ## Follow worker logs only
	$(DC) logs -f --tail=100 worker

logs-nginx: ## Follow nginx logs only
	$(DC) logs -f --tail=100 nginx

# ── Shell Access ────────────────────────────────────────────────────────────
shell-backend: ## Open a bash shell in the backend container
	docker exec -it pypress-backend bash

shell-db: ## Open a psql shell in the database
	docker exec -it pypress-db psql -U $${DB_USER:-pypress} -d $${DB_NAME:-pypress}

shell-redis: ## Open a redis-cli shell
	docker exec -it pypress-redis redis-cli -a $${REDIS_PASSWORD:-pypress_redis_dev}

# ── Database ────────────────────────────────────────────────────────────────
migrate: ## Run pending database migrations
	docker exec pypress-backend alembic upgrade head
	@echo "Migrations applied."

migrate-create: ## Create a new migration (usage: make migrate-create name=add_seo_table)
	@if [ -z "$(name)" ]; then echo "Usage: make migrate-create name=migration_name"; exit 1; fi
	docker exec pypress-backend alembic revision --autogenerate -m "$(name)"
	@echo "Migration created: $(name)"

seed-demo: ## Populate with sample content (posts, pages, users, categories)
	docker exec pypress-backend python -m app.scripts.seed_demo
	@echo "Demo data seeded."

# ── Testing ─────────────────────────────────────────────────────────────────
test: ## Run the full test suite
	$(DC_TEST) up --build --abort-on-container-exit --exit-code-from backend
	$(DC_TEST) down -v
	@echo "Tests complete."

# ── Backup & Restore ───────────────────────────────────────────────────────
backup: ## Create an immediate database backup
	@TIMESTAMP=$$(date +%Y-%m-%d_%H-%M-%S) && \
	docker exec pypress-db pg_dump -U $${DB_USER:-pypress} -d $${DB_NAME:-pypress} \
		--format=custom --compress=9 -f /tmp/backup_$$TIMESTAMP.dump && \
	docker cp pypress-db:/tmp/backup_$$TIMESTAMP.dump ./backups/backup_$$TIMESTAMP.dump && \
	echo "Backup saved: ./backups/backup_$$TIMESTAMP.dump"

backup-list: ## List all available backups
	@echo "Available backups:"
	@ls -lh ./backups/*.dump 2>/dev/null || echo "  No backups found."

restore: ## Restore from a backup (usage: make restore backup=2026-03-05_14-30-00)
	@if [ -z "$(backup)" ]; then echo "Usage: make restore backup=TIMESTAMP"; exit 1; fi
	@echo "WARNING: This will replace the current database!"
	@read -p "Continue? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	docker cp ./backups/backup_$(backup).dump pypress-db:/tmp/restore.dump
	docker exec pypress-db pg_restore -U $${DB_USER:-pypress} -d $${DB_NAME:-pypress} \
		--clean --if-exists /tmp/restore.dump
	@echo "Database restored from backup: $(backup)"

# ── Health & Status ─────────────────────────────────────────────────────────

# ── SSL / HTTPS ────────────────────────────────────────────────────────────
ssl-setup: check-env ## Set up Let's Encrypt SSL certificate (usage: make ssl-setup)
	@bash scripts/ssl-setup.sh

ssl-renew: ## Renew SSL certificate (safe to run anytime; skips if not needed)
	@bash scripts/ssl-renew.sh

# ── Validation ─────────────────────────────────────────────────────────────
validate-networks: ## Verify Docker network isolation (backend has no public access)
	@bash scripts/validate-networks.sh

# ── Health & Status ─────────────────────────────────────────────────────────
health: ## Run health checks on all services
	@echo "PyPress Health Check"
	@echo "==================="
	@echo ""
	@for svc in db redis backend worker frontend admin nginx; do \
		STATUS=$$(docker inspect --format='{{.State.Health.Status}}' pypress-$$svc 2>/dev/null || echo "not running"); \
		if [ "$$STATUS" = "healthy" ]; then \
			echo "  ✅ $$svc: $$STATUS"; \
		elif [ "$$STATUS" = "not running" ]; then \
			echo "  ⬛ $$svc: not running"; \
		else \
			echo "  ❌ $$svc: $$STATUS"; \
		fi; \
	done
	@echo ""

status: ## Show status of all containers
	$(DC) ps

# ── Code Quality ────────────────────────────────────────────────────────────
lint: ## Run linters (ruff for Python, eslint for JS/TS)
	docker exec pypress-backend ruff check app/
	@echo "Backend lint complete."

format: ## Auto-format code (ruff format for Python, prettier for JS/TS)
	docker exec pypress-backend ruff format app/
	@echo "Backend formatted."

type-check: ## Run type checking (mypy for Python)
	docker exec pypress-backend mypy app/ --ignore-missing-imports
	@echo "Type check complete."

# ── Cleanup ─────────────────────────────────────────────────────────────────
clean: ## Remove all containers, images, and volumes (DESTRUCTIVE!)
	@echo "WARNING: This will DELETE all PyPress data (database, uploads, everything)!"
	@read -p "Are you absolutely sure? Type 'yes' to confirm: " confirm && \
		[ "$$confirm" = "yes" ] || exit 1
	$(DC_DEV) down -v --rmi all 2>/dev/null; \
	$(DC) down -v --rmi all 2>/dev/null; \
	docker volume rm pypress-pgdata pypress-redis-data pypress-uploads \
		pypress-plugins pypress-themes pypress-backups pypress-logs 2>/dev/null; \
	echo "Everything cleaned. Run 'make dev' to start fresh."
