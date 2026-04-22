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
- [Integración con el frontend](#integración-con-el-frontend)
- [Seguridad](#seguridad)
- [Testing](#testing)
- [Comandos (Makefile)](#comandos-makefile)
- [CI/CD](#cicd)
- [Documentación adicional](#documentación-adicional)
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

**Opción recomendada — Docker Compose (todo en uno, migraciones automáticas):**

```bash
git clone https://github.com/Dev3Core/erp-backend.git
cd erp-backend
cp .env.example .env
# Generar JWT_SECRET (>= 64 chars) y pegarlo en .env:
python -c "import secrets; print(secrets.token_urlsafe(64))"
make dev
```

`make dev` levanta Postgres + Redis + un job `migrate` (que corre `alembic upgrade head`) + API con hot-reload + worker ARQ. El `api` y el `worker` dependen de `migrate: service_completed_successfully`, por lo que cada `docker compose up` aplica migraciones pendientes antes de arrancar la app.

> `JWT_SECRET` es **obligatorio** y debe tener al menos 64 caracteres. La app falla al arrancar si falta o contiene un placeholder.

API: `http://localhost:8000` · OpenAPI: `http://localhost:8000/docs` · Health: `http://localhost:8000/api/v1/health`.

**Opción sin Docker (host local):**

```bash
poetry install --with dev
cp .env.example .env                                              # + setear JWT_SECRET
docker compose -f .docker/compose.yml up postgres redis -d       # solo infra
make migrate                                                       # alembic upgrade head
poetry run uvicorn app.main:app --reload --port 8000              # API
poetry run arq app.workers.tasks.WorkerSettings                   # worker (otra terminal)
```

---

## Ejecución con Docker

### Desarrollo (hot-reload)

```bash
make dev
# equivalente: docker compose -f .docker/compose.yml up --build
```

Servicios que se levantan:

| Servicio  | Rol                                                                 |
|-----------|---------------------------------------------------------------------|
| postgres  | Base de datos                                                       |
| redis     | Cache + broker ARQ                                                  |
| migrate   | Job one-shot (`alembic upgrade head`). `api` y `worker` lo esperan  |
| api       | FastAPI con hot-reload (puerto 8000)                                |
| worker    | ARQ worker para jobs en background                                  |

Monta `app/`, `alembic/` y `tests/` como volúmenes. Cambios se reflejan sin rebuild. Cada `docker compose up` vuelve a correr `migrate`, que es idempotente — aplica solo las migraciones pendientes.

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

| Método | Ruta                   | Descripción                                               | Auth     | Rate limit       |
|--------|------------------------|-----------------------------------------------------------|----------|------------------|
| POST   | `/register`            | Crea tenant + owner. Retorna IDs y slug                   | Público  | 3 / min / IP     |
| POST   | `/login`               | Login; setea `access_token` + `refresh_token` cookies     | Público  | 5 / min / IP     |
| POST   | `/refresh`             | Rota access + refresh, blacklistea el anterior            | Cookie   | —                |
| POST   | `/logout`              | Invalida tokens en Redis (blacklist)                      | Cookie   | —                |
| GET    | `/me`                  | Datos de sesión (rol, tenant, slug, flags)                | JWT      | —                |
| POST   | `/mfa/setup`           | Genera secreto TOTP + `otpauth://` URI                    | JWT      | —                |
| POST   | `/mfa/verify`          | Valida código TOTP; activa MFA en primer verify            | JWT      | 5 / min / user   |
| POST   | `/api-keys`            | Emite API key efímera (extensión Chrome). Retorna el plaintext una sola vez | JWT | — |
| GET    | `/api-keys`            | Lista las keys del usuario actual                         | JWT      | —                |
| DELETE | `/api-keys/{id}`       | Revoca una key propia                                     | JWT      | —                |

### Recursos tenant-scoped (OWNER/ADMIN write; read varía por rol)

| Método / Ruta | Descripción |
|-------------|-------------|
| `POST/GET/PATCH/DELETE /users` | Gestiona usuarios del estudio (MONITOR/MODEL). OWNER no asignable; solo OWNER puede promover a ADMIN |
| `POST/GET/PATCH/DELETE /rooms` | Cuentas de Chaturbate/Stripchat (soft delete, unique por plataforma+url) |
| `POST/GET/PATCH/DELETE /split-configs` | % platform/studio/model (suma 100, un default por tenant) |
| `POST/GET/PATCH/DELETE /technical-sheets` | Ficha de modelo (bio, idiomas, categorías, notas) |
| `POST/GET/PATCH/DELETE /shifts` | Turnos (model + room + monitor opcional + tiempos) |

### Liquidaciones y sueldos

| Método / Ruta | Descripción |
|-------------|-------------|
| `POST /liquidations/from-shift` | Crea liquidación desde shift FINISHED: aplica split, convierte USD→COP con TRM |
| `GET /liquidations` | Lista con filtros por status, rango de fechas, shift_id |
| `PATCH /liquidations/{id}` | Transición de estado: PENDING → APPROVED → PAID (y APPROVED ↔ PENDING) |
| `DELETE /liquidations/{id}` | Elimina (bloqueado si PAID) |
| `POST/GET/DELETE /monitor-salaries` | Historial de sueldos por monitor (append-only) |
| `GET /monitor-salaries/current/{monitor_id}` | Sueldo vigente en una fecha |

### Métricas (owner dashboard)

| Método / Ruta | Descripción |
|-------------|-------------|
| `GET /metrics/overview` | Totales de shifts/tokens/USD y conteo de liquidaciones por status |
| `GET /metrics/revenue-by-model` | Ranking de modelos por USD generado |
| `GET /metrics/revenue-by-monitor` | Ranking de monitores (vía shifts asignados) |

### TRM / Tasa de cambio

| Método / Ruta | Descripción |
|-------------|-------------|
| `GET /exchange-rates/today` | TRM vigente hoy (cache-aside contra datos.gov.co) |
| `GET /exchange-rates/{date}` | TRM para una fecha específica |
| `POST /exchange-rates` | Override manual (admin/owner) |

### `/api/v1`

| Método | Ruta       | Descripción    | Auth    |
|--------|------------|----------------|---------|
| GET    | `/health`  | Health check   | Público |

Documentación interactiva completa en `/docs` (Swagger) y `/redoc` (ReDoc).

---

## Integración con el frontend

Guía completa paso a paso (Next.js 16 / React) en [`docs/frontend-auth.md`](docs/frontend-auth.md). Cubre:

- Flujo login → `GET /auth/me` → store de sesión.
- Tipado de `Me` + ejemplo con Zustand.
- Hook `useHasRole(...)` para gating de UI.
- Cuándo refrescar `/me` (bootstrap, tras MFA, etc.).
- Interceptor de 401 y refresh automático del access token.
- Protección de rutas en Next.js: middleware + layout cliente + server components.
- CORS + cookies cross-origin en producción.

Resumen rápido:

| Necesidad del front              | De dónde la saca                                  |
|----------------------------------|---------------------------------------------------|
| ¿Hay sesión activa?              | `GET /auth/me` devuelve 200 vs 401                |
| Rol del usuario                  | `me.role` del store (tras `/auth/me`)             |
| Tenant + slug del estudio        | `me.tenant_id`, `me.studio_slug`                  |
| Decisiones de UX (mostrar botón) | Rol del store — **nunca** es decisión de seguridad |
| Authorization real               | Backend revalida cada request contra DB → 403     |

> Las cookies son `HttpOnly`: el JavaScript del front **no puede** leer el JWT. No intentes decodificarlo, llama `/auth/me`.

---

## Seguridad

### Medidas activas

| Capa                | Control                                                                                      |
|---------------------|----------------------------------------------------------------------------------------------|
| Transport           | HSTS (`max-age=63072000`), cookies `Secure` en prod, CORS con allowlist explícita            |
| Headers             | CSP `default-src 'self'; frame-ancestors 'none'`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, COOP, CORP, `Permissions-Policy` |
| Autenticación       | argon2 password hashing, JWT firmado HS256 con payload mínimo (solo `sub` + flags de sesión; rol y tenant se leen de DB en cada request y se exponen al front vía `GET /auth/me`), rotación de refresh token, blacklist Redis |
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

Estado actual: **100 tests** cubriendo auth, MFA, rate limiting, security headers, audit log, todos los CRUDs tenant-scoped (users, rooms, split-configs, technical-sheets, shifts), liquidaciones (incluyendo cálculo USD→COP y transiciones de estado), sueldos de monitores con historial, métricas agregadas del dashboard, API keys, exchange rates con fetcher mock, y asilamiento multi-tenant (tenant A no accede a recursos de tenant B).

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

## Documentación adicional

La carpeta [`docs/`](docs/) contiene guías largas que no caben en el README:

| Documento | Contenido |
|-----------|-----------|
| [`docs/frontend-auth.md`](docs/frontend-auth.md) | Cómo consumir la API desde el frontend — login, `GET /auth/me`, store, refresh, protección de rutas. |

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
