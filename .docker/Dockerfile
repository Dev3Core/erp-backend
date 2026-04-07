# ============================================================================
# Production Dockerfile — erp-webcam-backend
# Multi-stage: builder installs deps, production copies only the venv.
# ============================================================================

FROM python:3.12-slim@sha256:6294405dc2a6612366092848c41c2ec7f9ba7368b618ee707dcf7f75c1d07830 AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=2.3.3 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

WORKDIR /build

COPY pyproject.toml poetry.lock ./

RUN poetry install --only=main --no-root --no-directory

COPY app ./app

RUN poetry install --only=main

# ============================================================================
FROM python:3.12-slim@sha256:6294405dc2a6612366092848c41c2ec7f9ba7368b618ee707dcf7f75c1d07830 AS production

LABEL maintainer="erp-team" \
      org.opencontainers.image.source="https://github.com/tu-org/erp-backend" \
      org.opencontainers.image.description="ERP Webcam Backend API"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN groupadd --system --gid 1000 appuser && \
    useradd --system --uid 1000 --gid appuser --no-create-home --shell /usr/sbin/nologin appuser && \
    mkdir -p /app && chown appuser:appuser /app

WORKDIR /app

COPY --from=builder --chown=appuser:appuser /build/.venv ./.venv
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser alembic ./alembic
COPY --chown=appuser:appuser alembic.ini ./alembic.ini

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--access-log"]
