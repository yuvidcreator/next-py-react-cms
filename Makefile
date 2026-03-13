.PHONY: up down restart logs shell-backend shell-db migrate backup restore test

up:
# 	docker compose up -d
	docker compose up

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f $(service)

shell-backend:
	docker compose exec backend python -c "import code; code.interact(local=locals())"

shell-db:
	docker compose exec db psql -U pypress

test:
	docker compose exec backend pytest

deploy: up migrate
	@echo "PyPress deployed! Backend: http://localhost:8000/api/docs"

migrate:
	@echo "Migrations will be implemented with Alembic in Phase 2"
