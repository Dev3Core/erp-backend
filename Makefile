.PHONY: dev dev-down prod prod-down migrate lint test shell security-scan sast sca secrets-scan secrets-audit semgrep-scan

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

# --- Security ---
sast:
	poetry run bandit -r app/ -c pyproject.toml
	poetry run ruff check --select S app/

sca:
	poetry run pip-audit --skip-editable

secrets-scan:
	poetry run detect-secrets scan --baseline .secrets.baseline --exclude-files '\.venv|poetry\.lock|\.lock$$'

secrets-audit:
	poetry run detect-secrets audit .secrets.baseline

semgrep-scan:
	poetry run semgrep --config=p/owasp-top-ten --config=p/python --config=p/security-audit --error app/

security-scan: sast sca secrets-scan semgrep-scan

# --- Utilities ---
shell:
	$(COMPOSE_DEV) exec api bash

install:
	poetry install
