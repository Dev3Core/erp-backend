# ERP Webcam — Backend

Backend multi-tenant SaaS para la gestión integral de estudios webcam: autenticación con MFA, control de turnos, liquidaciones, automatizaciones y auditoría. Construido sobre FastAPI (async) con arquitectura por capas y foco en seguridad por defecto (OWASP Top 10).

[![CI](https://github.com/Dev3Core/erp-backend/actions/workflows/ci.yml/badge.svg)](https://github.com/Dev3Core/erp-backend/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-Proprietary-lightgrey)](#licencia)

---

## Tabla de contenidos

- [Características](#características)
- [Stack tecnológico](#stack-tecnológico)
- [Arquitectura](#arquitectura)
- [Requisitos](#requisitos)
- [Inicio rápido](#inicio-rápido)
- [Ejecución con Docker](#ejecución-con-docker)
- [Variables de entorno](#variables-de-entorno)
- [API](#api)
- [Seguridad](#seguridad)
- [Testing](#testing)
- [Comandos (Makefile)](#comandos-makefile)
- [CI/CD](#cicd)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Contribuir](#contribuir)
- [Licencia](#licencia)

---

## Características

- **Multi-tenant** — aislamiento por `tenant_id` en cada tabla y consulta ORM.
- **Autenticación robusta** — argon2 para passwords, JWT en cookies `HttpOnly` + `SameSite`, refresh con rotación y blacklist en Redis, MFA TOTP opcional.
- **RBAC** — roles `OWNER` / `ADMIN` / `MODEL` via dependencias (`CurrentUser`, `require_roles`, `MFAVerifiedUser`).
- **Rate limiting** — Redis-backed, por IP o por usuario, configurable por endpoint.
- **Headers de seguridad** — middleware inyecta CSP, HSTS, `X-Frame-Options: DENY`, COOP, CORP, `Permissions-Policy`, etc.
- **Audit log** — escritura en sesión independiente para sobrevivir a rollback de la transacción principal (eventos fallidos no se pierden).
- **Workers async** — ARQ + Redis para jobs en background (scraping con Playwright, procesamiento de liquidaciones).
- **Calidad y seguridad automatizadas** — SAST (bandit + ruff-S), SCA (pip-audit), secrets (detect-secrets + baseline), reglas OWASP (semgrep). Integrado en CI.

---

## Stack tecnológico

| Componente        | Tecnología                                                      |
|-------------------|-----------------------------------------------------------------|
| Framework web     | [FastAPI](https://fastapi.tiangolo.com/) 0.136                  |
| Lenguaje          | Python 3.12+                                                    |
| Base de datos     | PostgreSQL 16 (driver `asyncpg`)                                |
| ORM               | SQLAlchemy 2.0 (async)                                          |
| Migraciones       | Alembic                                                         |
| Cache / broker    | Redis 7                                                         |
| Workers           | [ARQ](https://arq-docs.helpmanual.io/)                          |
| Automatización    | Playwright                                                      |
| Auth              | argon2-cffi + python-jose (JWT) + pyotp (TOTP)                  |
| Validación        | Pydantic v2 + pydantic-settings                                 |
| HTTP client       | httpx (async)                                                   |
| Gestor deps       | Poetry 2.3+                                                     |
| Lint / format     | Ruff                                                            |
| Seguridad         | bandit, pip-audit, semgrep, detect-secrets                      |
| Testing           | pytest + pytest-asyncio + httpx + fakeredis + aiosqlite         |
| Contenedores      | Docker + Compose                                                |

---

## Arquitectura

Separación estricta por capas (imports solo hacia abajo):

```
app/api/v1/*      Controllers finos: parsear -> llamar servicio -> formar respuesta
    v
app/services/*    Reglas de negocio, transacciones, orquestación
    v
app/core/*        Seguridad, dependencias, middleware, tenant, rate-limit
    v
app/models/*      ORM (datos)         app/schemas/*     Pydantic (I/O)
    v
app/config.py  ·  app/database.py  ·  app/redis.py      Infraestructura
```

Reglas aplicadas:
- `models/` y `schemas/` no importan lógica de negocio.
- `services/` no depende de `api/`. No lanza `HTTPException`; levanta excepciones de dominio (`AuthError`) mapeadas en el controller.
- Inyección de dependencias vía FastAPI `Depends` (una sesión DB por request).

Detalles en [.claude/skills/clean-architecture/SKILL.md](.claude/skills/clean-architecture/SKILL.md).

---

## Requisitos

- Python **3.12+**
- [Poetry **2.3+**](https://python-poetry.org/docs/#installation)
- Docker + Docker Compose (opcional para desarrollo local completo)
- Make (opcional, atajos de comandos)
- PostgreSQL 16 y Redis 7 si no se usa Docker

---

## Inicio rápido

### 1. Clonar e instalar

```bash
git clone https://github.com/Dev3Core/erp-backend.git
cd erp-backend
poetry install --with dev
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(64))"  # generar JWT_SECRET
# Pegar el valor generado en JWT_SECRET dentro de .env
```

> `JWT_SECRET` es **obligatorio** y debe tener al menos 64 caracteres. La app falla al arrancar si falta o contiene un placeholder.

### 3. Levantar infraestructura

```bash
docker compose -f .docker/compose.yml up postgres redis -d
```

### 4. Aplicar migraciones

```bash
make migrate
# o: poetry run alembic upgrade head
```

### 5. Servidor de desarrollo

```bash
poetry run uvicorn app.main:app --reload --port 8000
```

### 6. Worker ARQ (terminal aparte)

```bash
poetry run arq app.workers.tasks.WorkerSettings
```

API: `http://localhost:8000` · OpenAPI: `http://localhost:8000/docs` · Health: `http://localhost:8000/api/v1/health`.

---

## Ejecución con Docker

### Desarrollo (hot-reload)

```bash
make dev
# equivalente: docker compose -f .docker/compose.yml up --build
```

Monta `app/`, `alembic/` y `tests/` como volúmenes. Cambios se reflejan sin rebuild.

### Producción

```bash
cp .env.production.example .env.production
# Editar con valores reales, incluyendo SESSION_COOKIE_SECURE=true
make prod
```

Diferencias con desarrollo:
- Multi-stage build, solo deps de producción.
- Usuario non-root sin shell.
- Filesystem read-only (`tmpfs` en `/tmp`).
- Límites de CPU/memoria por servicio.
- Redis con password y política de `maxmemory`.
- Red aislada: Postgres/Redis sin puertos expuestos al host.
- Restart policy con backoff.

---

## Variables de entorno

### Desarrollo (`.env`)

| Variable                      | Obligatoria | Descripción                                    | Default                                                             |
|-------------------------------|:-----------:|------------------------------------------------|---------------------------------------------------------------------|
| `DATABASE_URL`                | No          | String de conexión a PostgreSQL (asyncpg)      | `postgresql+asyncpg://erp:erp_local@localhost:5432/erp_webcam`      |
| `REDIS_URL`                   | No          | String de conexión a Redis                     | `redis://localhost:6379`                                            |
| `JWT_SECRET`                  | **Sí**      | Clave HS256, `len >= 64`                       | —                                                                   |
| `JWT_ALGORITHM`               | No          | Algoritmo JWT                                  | `HS256`                                                             |
| `JWT_EXPIRES_MINUTES`         | No          | TTL access token (min)                         | `15`                                                                |
| `JWT_REFRESH_EXPIRES_MINUTES` | No          | TTL refresh token (min)                        | `10080` (7 días)                                                    |
| `CORS_ORIGINS`                | No          | Orígenes permitidos (lista JSON)               | `["http://localhost:3000"]`                                         |
| `SESSION_COOKIE_SECURE`       | No          | Flag `Secure` en cookies (true en producción) | `false`                                                             |
| `DEBUG`                       | No          | Modo debug                                     | `false`                                                             |

### Producción adicionales (`.env.production`)

| Variable            | Descripción                   |
|---------------------|-------------------------------|
| `POSTGRES_USER`     | Usuario de PostgreSQL         |
| `POSTGRES_PASSWORD` | Password de PostgreSQL        |
| `POSTGRES_DB`       | Nombre de la base de datos    |
| `REDIS_PASSWORD`    | Password de Redis             |
| `API_PORT`          | Puerto expuesto de la API     |

---

## API

### `/api/v1/auth`

| Método | Ruta           | Descripción                                         | Auth     | Rate limit       |
|--------|----------------|-----------------------------------------------------|----------|------------------|
| POST   | `/register`    | Crea tenant + owner. Retorna IDs y slug             | Público  | 3 / min / IP     |
| POST   | `/login`       | Login; setea `access_token` + `refresh_token` cookies | Público  | 5 / min / IP     |
| POST   | `/refresh`     | Rota access + refresh, blacklistea el anterior      | Cookie   | —                |
| POST   | `/logout`      | Invalida tokens en Redis (blacklist)                | Cookie   | —                |
| POST   | `/mfa/setup`   | Genera secreto TOTP + `otpauth://` URI              | JWT      | —                |
| POST   | `/mfa/verify`  | Valida código TOTP; activa MFA en primer verify      | JWT      | 5 / min / user   |

### `/api/v1`

| Método | Ruta       | Descripción    | Auth    |
|--------|------------|----------------|---------|
| GET    | `/health`  | Health check   | Público |

Documentación interactiva completa en `/docs` (Swagger) y `/redoc` (ReDoc).

---

## Seguridad

### Medidas activas

| Capa                | Control                                                                                      |
|---------------------|----------------------------------------------------------------------------------------------|
| Transport           | HSTS (`max-age=63072000`), cookies `Secure` en prod, CORS con allowlist explícita            |
| Headers             | CSP `default-src 'self'; frame-ancestors 'none'`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, COOP, CORP, `Permissions-Policy` |
| Autenticación       | argon2 password hashing, JWT firmado HS256, rotación de refresh token, blacklist Redis       |
| Sesiones            | Cookies `HttpOnly` + `SameSite=Lax` + `Secure` (prod)                                        |
| MFA                 | TOTP (pyotp), verificación obligatoria para acciones sensibles                               |
| Rate limiting       | Redis INCR/EXPIRE por IP o user id en endpoints críticos; responde 429 + `Retry-After`       |
| Validación input    | Pydantic v2 en todo body; `EmailStr`, `SecretStr`, `constr(min_length=...)` donde aplica     |
| SQLi                | SQLAlchemy 2.0 expressions; prohibido `text()` con interpolación                             |
| Secrets             | Solo vía `pydantic-settings`; `.env` fuera de git; `detect-secrets` con baseline en CI       |
| Audit trail         | `AuditLog` por evento auth; sesión separada para no perder trazas en rollback                |
| Logs                | Sin tokens, passwords ni PII; errores internos no se exponen al cliente                      |

### Herramientas de seguridad

| Tipo      | Herramienta       | Target                                        |
|-----------|-------------------|-----------------------------------------------|
| SAST      | bandit            | `app/` — vulnerabilidades Python comunes      |
| SAST      | ruff `--select S` | reglas bandit embebidas en ruff (rápido)      |
| SAST      | semgrep           | reglas OWASP Top 10 + Python + security-audit |
| SCA       | pip-audit         | CVEs en dependencias                          |
| Secrets   | detect-secrets    | secretos hardcodeados; baseline en repo       |

Ejecutables de una sola vez o en CI:

```bash
make sast           # bandit + ruff-S
make sca            # pip-audit
make secrets-scan   # detect-secrets vs baseline
make semgrep-scan   # reglas OWASP
make security-scan  # los cuatro anteriores en secuencia
```

Actualizar la baseline de secrets (tras aceptar un placeholder nuevo):

```bash
poetry run detect-secrets scan > .secrets.baseline
make secrets-audit    # auditoría interactiva de la baseline
```

### Reporte de vulnerabilidades

Ante hallazgos que afecten confidencialidad o integridad, abrir un issue privado en [GitHub Security Advisories](https://github.com/Dev3Core/erp-backend/security/advisories/new). **No** reportar por issues públicos.

---

## Testing

```bash
make test                      # suite completa
poetry run pytest tests/api/   # solo tests de API
poetry run pytest -k auth -v   # filtro por nombre
```

Estado actual: **30 tests** cubriendo auth (registro, login, refresh, logout, MFA), rate limiting, security headers y audit log.

Las pruebas usan SQLite en memoria (`aiosqlite`) y una implementación ligera de Redis (`FakeRedis`) — cero dependencias externas.

---

## Comandos (Makefile)

### Desarrollo y operación

| Comando                          | Descripción                                       |
|----------------------------------|---------------------------------------------------|
| `make dev`                       | Entorno de desarrollo (Docker Compose)             |
| `make dev-down`                  | Apagar entorno de desarrollo                       |
| `make dev-logs`                  | Logs de la API (dev)                               |
| `make prod`                      | Entorno de producción                              |
| `make prod-down` / `make prod-logs` | Apagar / ver logs en producción                |
| `make shell`                     | Shell dentro del contenedor API                    |
| `make install`                   | `poetry install`                                   |

### Base de datos

| Comando                             | Descripción                         |
|-------------------------------------|-------------------------------------|
| `make migrate`                      | Aplica migraciones pendientes       |
| `make migration msg="descripcion"`  | Genera nueva migración autogenerada |

### Calidad

| Comando         | Descripción                                    |
|-----------------|------------------------------------------------|
| `make lint`     | `ruff check` + `ruff format --check`           |
| `make lint-fix` | Autofix + format                               |
| `make test`     | Suite completa con `pytest -v`                 |

### Seguridad

| Comando               | Descripción                                             |
|-----------------------|---------------------------------------------------------|
| `make sast`           | bandit + reglas S de ruff                               |
| `make sca`            | pip-audit (CVEs)                                        |
| `make secrets-scan`   | detect-secrets contra `.secrets.baseline`               |
| `make semgrep-scan`   | semgrep con OWASP Top 10 + python + security-audit      |
| `make security-scan`  | ejecuta los cuatro anteriores                           |
| `make secrets-audit`  | auditoría interactiva de la baseline                    |

---

## CI/CD

GitHub Actions corre dos jobs en paralelo en cada PR hacia `main`:

1. **`lint-and-test`** — `ruff check`, `ruff format --check`, y `pytest -v` contra Postgres 16 + Redis 7 (containers de servicio).
2. **`security-scan`** — SAST (bandit + ruff-S), SCA (pip-audit), secrets (detect-secrets vs baseline), y Semgrep OWASP.

Cualquiera que falle bloquea el merge. Configuración en [.github/workflows/ci.yml](.github/workflows/ci.yml).

---

## Estructura del proyecto

```
erp-backend/
├── .claude/                        # Skills + agents del workspace (team config)
│   ├── agents/                     # security-auditor, security-scanner, architecture-reviewer
│   └── skills/                     # secure-coding, clean-architecture
├── .docker/                        # Configuración Docker
│   ├── Dockerfile                  # Imagen producción (multi-stage)
│   ├── Dockerfile.dev              # Imagen desarrollo (hot-reload)
│   ├── compose.yml                 # Compose desarrollo
│   └── compose.prod.yml            # Compose producción
├── .github/workflows/ci.yml        # Pipeline CI (lint + test + security)
├── alembic/                        # Migraciones de DB
├── app/
│   ├── api/v1/                     # Controllers HTTP
│   │   ├── auth.py                 # Login, refresh, logout, MFA
│   │   ├── health.py
│   │   └── router.py
│   ├── core/                       # Cross-cutting
│   │   ├── dependencies.py         # CurrentUser, require_roles, MFAVerifiedUser
│   │   ├── middleware.py           # SecurityHeadersMiddleware
│   │   ├── rate_limit.py           # RateLimitByIP / ByUser
│   │   ├── security.py             # Password hashing, JWT
│   │   └── tenant.py               # Tenant context
│   ├── models/                     # SQLAlchemy ORM
│   ├── schemas/                    # Pydantic DTOs
│   ├── services/                   # Reglas de negocio
│   ├── workers/                    # Jobs ARQ (Playwright, etc.)
│   ├── config.py                   # Settings (pydantic-settings)
│   ├── database.py
│   ├── redis.py
│   └── main.py                     # FastAPI factory + middlewares
├── tests/
│   ├── api/
│   │   ├── test_auth.py
│   │   ├── test_audit_log.py
│   │   ├── test_health.py
│   │   ├── test_rate_limit.py
│   │   └── test_security_headers.py
│   └── conftest.py
├── .env.example
├── .env.production.example
├── .secrets.baseline               # Baseline de detect-secrets
├── Makefile
├── pyproject.toml                  # Poetry + config de herramientas
├── poetry.lock
└── ruff.toml
```

---

## Contribuir

1. Fork o branch desde `main`.
2. `poetry install --with dev && pre-commit install`.
3. Código nuevo requiere tests. Ejecutar `make lint`, `make test` y `make security-scan` antes de abrir PR.
4. Seguir los estándares del repo:
   - OWASP Top 10 — ver [.claude/skills/secure-coding/SKILL.md](.claude/skills/secure-coding/SKILL.md)
   - SOLID + capas limpias — ver [.claude/skills/clean-architecture/SKILL.md](.claude/skills/clean-architecture/SKILL.md)
5. PR contra `main`. El CI (`lint-and-test` + `security-scan`) debe pasar.

Commits: formato libre pero descriptivo. Preferir [Conventional Commits](https://www.conventionalcommits.org/).

---

## Licencia

Proprietary — todos los derechos reservados. Ver [LICENSE](LICENSE) si aplica.
