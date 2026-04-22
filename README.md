# ERP Webcam — Backend

Backend multi-tenant SaaS para la gestión integral de estudios webcam: autenticación con MFA, control de turnos, liquidaciones, automatizaciones y auditoría. FastAPI (async) sobre arquitectura por capas con OWASP Top 10 como requisito no negociable.

[![CI](https://github.com/Dev3Core/erp-backend/actions/workflows/ci.yml/badge.svg)](https://github.com/Dev3Core/erp-backend/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-Proprietary-lightgrey)](#licencia)

---

## Características

- **Multi-tenant** — aislamiento por `tenant_id` en cada tabla y consulta.
- **Auth robusta** — argon2, JWT en cookies HttpOnly, refresh con rotación + blacklist en Redis, MFA TOTP opcional, API keys efímeras para la extensión.
- **RBAC** — `OWNER` / `ADMIN` / `MONITOR` / `MODEL` via FastAPI dependencies.
- **Hardening de red** — CSP, HSTS, headers completos, CORS allowlisted, rate-limit Redis-backed.
- **Audit log** — eventos sensibles persistidos en sesión independiente (sobreviven a rollback).
- **Paginación centralizada** — offset para CRUDs bounded, cursor para time-series.
- **Chat real-time** — WebSocket por turno con persistencia.
- **Exports** — liquidaciones a PDF + CSV.
- **Seguridad automatizada en CI** — bandit, pip-audit, semgrep (OWASP), detect-secrets.

---

## Stack tecnológico

| Capa        | Tecnología                                        |
|-------------|---------------------------------------------------|
| API         | FastAPI 0.136 + Pydantic v2                       |
| ORM         | SQLAlchemy 2.0 async                              |
| DB          | PostgreSQL 16 (asyncpg)                           |
| Cache/Queue | Redis 7 + ARQ workers                             |
| Automación  | Playwright                                        |
| Auth        | argon2 + python-jose (HS256) + pyotp (TOTP)       |
| Deps        | Poetry 2.3+                                       |
| Testing     | pytest + pytest-asyncio + httpx + aiosqlite       |
| Infra       | Docker + Docker Compose                           |

---

## Arquitectura

```
api/ → services/ → core/ → models + schemas → config + database + redis
```

Imports van solo hacia abajo. `services/` nunca lanza `HTTPException`; routes mapean domain errors. Tenant isolation aplicada en cada query ORM. JWT lleva payload mínimo (sin rol ni tenant) — el backend re-lee ambos de DB en cada request.

Detalle, decisiones y árbol del proyecto en [`docs/architecture.md`](docs/architecture.md).

---

## Requisitos

- Python 3.12+
- [Poetry 2.3+](https://python-poetry.org/docs/#installation)
- Docker + Docker Compose (recomendado)

---

## Inicio rápido

```bash
git clone https://github.com/Dev3Core/erp-backend.git
cd erp-backend
cp .env.example .env
# Generar JWT_SECRET (>= 64 chars) y pegarlo en .env:
python -c "import secrets; print(secrets.token_urlsafe(64))"
make dev
```

`make dev` levanta postgres + redis + job `migrate` (one-shot `alembic upgrade head`) + api (hot-reload) + worker ARQ. Las migraciones son idempotentes y corren en cada `up`.

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/v1/health`

Setup sin Docker, variables de entorno completas y troubleshooting: [`docs/configuration.md`](docs/configuration.md).

---

## Documentación

| Documento | Para qué sirve |
|-----------|----------------|
| [`docs/api-reference.md`](docs/api-reference.md) | Catálogo completo de endpoints con auth + rate-limit. Source-of-truth en vivo: Swagger UI en `/docs` |
| [`docs/architecture.md`](docs/architecture.md) | Arquitectura por capas, patrones, flujo de request, estructura del proyecto, decisiones de diseño |
| [`docs/configuration.md`](docs/configuration.md) | Todas las variables de entorno (dev + prod) + troubleshooting |
| [`docs/security.md`](docs/security.md) | Controles OWASP Top 10, tooling (SAST/SCA/secrets), reporte responsable de vulnerabilidades |
| [`docs/pagination.md`](docs/pagination.md) | Contrato offset vs cursor, cuándo usar cada uno, plantillas para nuevos endpoints |
| [`docs/frontend-auth.md`](docs/frontend-auth.md) | Guía de consumo de la API desde Next.js (login, `/auth/me`, refresh, protección de rutas) |

---

## Testing

```bash
make test             # suite completa
poetry run pytest -k auth -v      # filtro por nombre
```

Estado actual: **149 tests** cubriendo auth/MFA, CRUDs tenant-scoped, liquidaciones con cálculo USD→COP y transiciones de estado, metrics, WebSocket chat, exports, pagination primitives y aislamiento multi-tenant cross-cutting. Usa SQLite en memoria + `FakeRedis` — cero dependencias externas en los tests.

---

## Comandos frecuentes

| Comando             | Descripción                                             |
|---------------------|---------------------------------------------------------|
| `make dev`          | Entorno de desarrollo (Docker Compose)                  |
| `make test`         | Suite de tests                                          |
| `make lint`         | `ruff check` + `ruff format --check`                    |
| `make migrate`      | Aplica migraciones contra la DB local                   |
| `make security-scan`| bandit + pip-audit + detect-secrets + semgrep           |

Lista completa en el [`Makefile`](Makefile).

---

## CI/CD

Cada PR contra `main` corre en paralelo:

1. **`lint-and-test`** — ruff + pytest contra Postgres 16 + Redis 7 reales.
2. **`security-scan`** — bandit + ruff-S + pip-audit + detect-secrets vs baseline + semgrep OWASP.

Ambos gatean el merge. Configuración en [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

---

## Contribuir

1. Branch desde `main`.
2. `poetry install --with dev && pre-commit install`.
3. Código nuevo con tests. Ejecutar `make lint`, `make test`, `make security-scan` antes del PR.
4. Seguir los estándares del workspace:
   - OWASP Top 10 → [`.claude/skills/secure-coding/SKILL.md`](.claude/skills/secure-coding/SKILL.md)
   - SOLID + capas → [`.claude/skills/clean-architecture/SKILL.md`](.claude/skills/clean-architecture/SKILL.md)
5. PR contra `main`; el CI debe pasar.

Commits en [Conventional Commits](https://www.conventionalcommits.org/).

---

## Licencia

Proprietary — todos los derechos reservados.
