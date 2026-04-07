# ERP Webcam Backend

Multi-tenant ERP SaaS backend for webcam studio management.

## Tech Stack

| Component      | Technology                      |
|----------------|---------------------------------|
| Framework      | FastAPI 0.115+                  |
| Language       | Python 3.12+                    |
| Database       | PostgreSQL 16 (asyncpg)         |
| ORM            | SQLAlchemy 2.0 (async)          |
| Migrations     | Alembic                         |
| Cache / Queue  | Redis 7 + ARQ                   |
| Auth           | argon2 + JWT (HttpOnly cookies) |
| MFA            | TOTP (pyotp)                    |
| HTTP Client    | httpx (async)                   |
| Automation     | Playwright                      |
| Validation     | Pydantic v2 + pydantic-settings |
| Deps           | Poetry 2.3+                     |
| Linting        | Ruff                            |
| Testing        | pytest + pytest-asyncio + httpx |
| Container      | Docker + Compose                |

## Prerequisites

- Python 3.12+
- [Poetry 2.3+](https://python-poetry.org/docs/#installation)
- Docker y Docker Compose
- Make (opcional, para atajos)

## Estructura del proyecto

```
erp-backend/
├── .docker/                        # Configuracion Docker
│   ├── Dockerfile                  # Imagen de produccion (multi-stage)
│   ├── Dockerfile.dev              # Imagen de desarrollo (hot-reload)
│   ├── compose.yml                 # Compose desarrollo
│   └── compose.prod.yml           # Compose produccion
├── .github/workflows/ci.yml       # Pipeline CI (lint + test)
├── app/                            # Codigo fuente
│   ├── api/v1/                     # Rutas versionadas
│   │   ├── auth.py                 # Login, refresh, logout, MFA
│   │   ├── health.py               # Health check
│   │   └── router.py               # Agregador de rutas v1
│   ├── core/                       # Utilidades transversales
│   │   ├── dependencies.py         # FastAPI deps (auth, roles, MFA)
│   │   ├── security.py             # JWT, hashing, blacklist keys
│   │   └── tenant.py               # Tenant context (ContextVar + middleware)
│   ├── models/                     # SQLAlchemy ORM models
│   ├── schemas/                    # Pydantic DTOs
│   ├── services/                   # Logica de negocio
│   │   └── auth.py                 # Servicio de autenticacion
│   ├── workers/                    # Tareas background (ARQ)
│   ├── config.py                   # Settings (pydantic-settings)
│   ├── database.py                 # Async engine + session
│   ├── redis.py                    # Redis connection pool
│   └── main.py                     # FastAPI factory + lifespan
├── alembic/                        # Migraciones de DB
├── tests/                          # Suite de tests
├── .dockerignore
├── .env.example                    # Template variables desarrollo
├── .env.production.example         # Template variables produccion
├── Makefile                        # Atajos de comandos
├── pyproject.toml                  # Poetry config + herramientas
└── poetry.lock                     # Dependencias pinneadas
```

## Setup local

### 1. Clonar e instalar dependencias

```bash
git clone https://github.com/tu-org/erp-backend.git
cd erp-backend
poetry install
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
```

Editar `.env` con los valores adecuados. Como minimo cambiar `JWT_SECRET`.

### 3. Levantar infraestructura (Postgres + Redis)

```bash
# Solo los servicios de infra, sin la app
docker compose -f .docker/compose.yml up postgres redis -d
```

### 4. Ejecutar migraciones

```bash
poetry run alembic upgrade head
```

### 5. Levantar el servidor de desarrollo

```bash
poetry run uvicorn app.main:app --reload --port 8000
```

### 6. Levantar el worker ARQ (terminal aparte)

```bash
poetry run arq app.workers.tasks.WorkerSettings
```

La API queda en `http://localhost:8000`. Docs en `http://localhost:8000/docs`.

## Docker

### Desarrollo

Levanta todo (Postgres, Redis, API con hot-reload, Worker):

```bash
make dev
# o directamente:
docker compose -f .docker/compose.yml up --build
```

Los volumenes montan `app/`, `alembic/` y `tests/` para hot-reload sin rebuild.

### Produccion

```bash
cp .env.production.example .env.production
# Editar .env.production con valores reales

make prod
# o directamente:
docker compose -f .docker/compose.prod.yml up -d --build
```

Diferencias con desarrollo:
- Multi-stage build, solo dependencias de produccion
- Usuario non-root sin shell
- Filesystem read-only (`tmpfs` para `/tmp`)
- Limites de CPU y memoria por servicio
- Redis con password y maxmemory policy
- Red aislada (Postgres/Redis sin puertos expuestos)
- Restart policy con backoff

## Comandos (Makefile)

| Comando                            | Descripcion                               |
|------------------------------------|-------------------------------------------|
| `make dev`                         | Levantar entorno de desarrollo             |
| `make dev-down`                    | Apagar entorno de desarrollo               |
| `make dev-logs`                    | Ver logs de la API (dev)                   |
| `make prod`                        | Levantar entorno de produccion             |
| `make prod-down`                   | Apagar entorno de produccion               |
| `make prod-logs`                   | Ver logs de la API (prod)                  |
| `make migrate`                     | Ejecutar migraciones pendientes            |
| `make migration msg="descripcion"` | Generar nueva migracion                    |
| `make lint`                        | Ejecutar linter (ruff check + format)      |
| `make lint-fix`                    | Corregir automaticamente errores de lint   |
| `make test`                        | Ejecutar tests                             |
| `make install`                     | Instalar dependencias con Poetry           |
| `make shell`                       | Abrir shell en el contenedor de la API     |

## API Endpoints

### Auth (`/api/v1/auth`)

| Metodo | Ruta           | Descripcion                                  | Auth |
|--------|----------------|----------------------------------------------|------|
| POST   | `/register`    | Crea tenant + owner. Retorna IDs y slug      | No   |
| POST   | `/login`       | Login con email/password. JWT en cookies HttpOnly | No |
| POST   | `/refresh`     | Rota access + refresh token                  | Cookie |
| POST   | `/logout`      | Invalida tokens en Redis                     | Cookie |
| POST   | `/mfa/setup`   | Genera secreto TOTP + URI para QR            | JWT  |
| POST   | `/mfa/verify`  | Valida codigo TOTP, activa MFA               | JWT  |

### Health (`/api/v1`)

| Metodo | Ruta      | Descripcion    | Auth |
|--------|-----------|----------------|------|
| GET    | `/health` | Health check   | No   |

## Variables de entorno

| Variable                     | Descripcion                        | Default                           |
|------------------------------|------------------------------------|-----------------------------------|
| `DATABASE_URL`               | PostgreSQL connection string       | `postgresql+asyncpg://erp:erp_local@localhost:5432/erp_webcam` |
| `REDIS_URL`                  | Redis connection string            | `redis://localhost:6379`          |
| `JWT_SECRET`                 | Clave para firmar JWT              | *(cambiar obligatoriamente)*      |
| `JWT_ALGORITHM`              | Algoritmo JWT                      | `HS256`                           |
| `JWT_EXPIRES_MINUTES`        | Expiracion access token (min)      | `15`                              |
| `JWT_REFRESH_EXPIRES_MINUTES`| Expiracion refresh token (min)     | `10080` (7 dias)                  |
| `CORS_ORIGINS`               | Origenes CORS permitidos (JSON)    | `["http://localhost:3000"]`       |
| `DEBUG`                      | Modo debug                         | `false`                           |

**Solo produccion** (`.env.production`):

| Variable           | Descripcion                 |
|--------------------|-----------------------------|
| `POSTGRES_USER`    | Usuario de PostgreSQL       |
| `POSTGRES_PASSWORD`| Password de PostgreSQL      |
| `POSTGRES_DB`      | Nombre de la base de datos  |
| `REDIS_PASSWORD`   | Password de Redis           |
| `API_PORT`         | Puerto expuesto de la API   |

## Contributing

1. Branch desde `main`
2. `pre-commit install` para activar hooks
3. Tests para funcionalidad nueva
4. `make lint` y `make test` deben pasar
5. PR contra `main`
