.PHONY: dev dev-down prod prod-down migrate lint test shell

COMPOSE_DEV  = docker compose -f .docker/compose.yml
COMPOSE_PROD = docker compose -f .docker/compose.prod.yml

# --- Development ---
dev:
	$(COMPOSE_DEV) up --build

dev-down:
	$(COMPOSE_DEV) down

dev-logs:
	$(COMPOSE_DEV) logs -f api

# --- Production ---
prod:
	$(COMPOSE_PROD) up -d --build

prod-down:
	$(COMPOSE_PROD) down

prod-logs:
	$(COMPOSE_PROD) logs -f api

# --- Database ---
migrate:
	poetry run alembic upgrade head

migration:
	poetry run alembic revision --autogenerate -m "$(msg)"

# --- Quality ---
lint:
	poetry run ruff check .
	poetry run ruff format --check .

lint-fix:
	poetry run ruff check --fix .
	poetry run ruff format .

test:
	poetry run pytest -v

# --- Utilities ---
shell:
	$(COMPOSE_DEV) exec api bash

install:
	poetry install
