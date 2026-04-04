# ERP Webcam Backend

Multi-tenant ERP SaaS backend for webcam studio management. Built with FastAPI, SQLAlchemy 2.0, and PostgreSQL.

## Tech Stack

| Component        | Technology                          |
|------------------|-------------------------------------|
| Framework        | FastAPI 0.115+                      |
| Language         | Python 3.12+                        |
| Database         | PostgreSQL 16 (asyncpg)             |
| ORM              | SQLAlchemy 2.0 (async)              |
| Migrations       | Alembic                             |
| Cache / Queue    | Redis 7 + ARQ                       |
| Auth             | argon2-cffi + python-jose (JWT)     |
| HTTP Client      | httpx (async)                       |
| Automation       | Playwright                          |
| Validation       | Pydantic v2 + pydantic-settings     |
| Linting          | Ruff                                |
| Testing          | pytest + pytest-asyncio + httpx     |
| Containerization | Docker + Docker Compose             |

## Prerequisites

- Python 3.12 or later
- PostgreSQL 16
- Redis 7
- Docker and Docker Compose (optional, for containerized setup)

## Local Setup

### With Docker (recommended)

```bash
cp .env.example .env
docker compose up -d
```

The API will be available at `http://localhost:8000`. OpenAPI docs at `http://localhost:8000/docs`.

### Without Docker

1. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -e ".[dev]"
```

3. Configure environment variables:

```bash
cp .env.example .env
# Edit .env with your local database and Redis connection details
```

4. Run database migrations:

```bash
alembic upgrade head
```

5. Start the development server:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

6. Start the ARQ worker (in a separate terminal):

```bash
arq app.workers.tasks.WorkerSettings
```

## Project Structure

```
app/
  main.py          - FastAPI application factory, lifespan, middleware
  config.py        - Application settings via pydantic-settings
  database.py      - Async SQLAlchemy engine and session management
  redis.py         - Redis connection pool management
  models/          - SQLAlchemy ORM models
  schemas/         - Pydantic request/response schemas
  api/v1/          - API route handlers (versioned)
  core/            - Security utilities, tenant context
  workers/         - ARQ background task definitions
alembic/           - Database migration scripts
tests/             - Test suite
```

## Running Tests

```bash
pytest -v
```

## Environment Variables

| Variable              | Description                        | Default                                                      |
|-----------------------|------------------------------------|--------------------------------------------------------------|
| `DATABASE_URL`        | PostgreSQL connection string       | `postgresql+asyncpg://erp:erp_local@localhost:5432/erp_webcam` |
| `REDIS_URL`           | Redis connection string            | `redis://localhost:6379`                                     |
| `JWT_SECRET`          | Secret key for JWT signing         | (must be changed in production)                              |
| `JWT_ALGORITHM`       | JWT signing algorithm              | `HS256`                                                      |
| `JWT_EXPIRES_MINUTES` | Access token expiration in minutes | `15`                                                         |
| `CORS_ORIGINS`        | Allowed CORS origins (JSON list)   | `["http://localhost:3000"]`                                  |
| `DEBUG`               | Enable debug mode                  | `false`                                                      |

## Contributing

1. Create a feature branch from `main`.
2. Install pre-commit hooks: `pre-commit install`.
3. Write tests for new functionality.
4. Ensure `ruff check .` and `ruff format --check .` pass.
5. Ensure all tests pass with `pytest -v`.
6. Open a pull request against `main`.
