# Architecture

## Layered by responsibility

```
app/api/v1/*      Controllers finos: parsear -> llamar servicio -> formar respuesta
    v
app/services/*    Reglas de negocio, transacciones, orquestación
    v
app/core/*        Seguridad, dependencias, middleware, tenant, rate-limit, pagination
    v
app/models/*      ORM (datos)          app/schemas/*    Pydantic (I/O contracts)
    v
app/config.py  ·  app/database.py  ·  app/redis.py        Infraestructura
```

**Regla de oro**: imports van de arriba hacia abajo. `models/` y `schemas/` nunca importan lógica de negocio. `services/` nunca importa `api/`. `HTTPException` solo se levanta en `api/`; los servicios lanzan excepciones de dominio (`ServiceError` y subclases) que los controllers mapean.

Detalle completo + anti-patrones: [`.claude/skills/clean-architecture/SKILL.md`](../.claude/skills/clean-architecture/SKILL.md).

## Patrones aplicados

| Patrón | Dónde | Por qué |
|--------|-------|---------|
| Dependency Injection vía FastAPI `Depends` | `CurrentUser`, `CurrentTenantId`, service factories, pagination params | Testabilidad + override en tests |
| Service layer | `app/services/*.py` | Reglas de negocio fuera de routes, reusables |
| Repository-lite | Queries viven en el service que owna el aggregate | Evita queries esparcidas |
| Unit of Work = 1 request = 1 session | `get_db` dependency | Transacciones atómicas por request |
| Independent session para audit | `AuthService._audit()` | Logs de failure path sobreviven al rollback principal |
| Domain errors | `app/services/errors.py` | `NotFoundError`, `ForbiddenError`, `ConflictError`, `ValidationError`, `ServiceError` base |
| Cursor pagination | Tables que crecen (chat, notifications, liquidations, shifts, reports) | O(1) por página, sin COUNT(*) |
| Offset pagination | CRUDs bounded | Estándar web, con cap de 5000 para DoS-protection |

## Flujo de una request típica

```
Cliente
   │ POST /api/v1/users  (cookie: access_token)
   ▼
SecurityHeadersMiddleware → inyecta HSTS/CSP/etc
   │
   ▼
CORS / auth decode (APIKeyCookie)  →  DB lookup User  →  CurrentUser
   │
   ▼
require_roles(OWNER, ADMIN) depends  →  ForbiddenError? → 403
   │
   ▼
Route handler:
  - Pydantic valida body (extra="forbid")
  - CurrentTenantId = user.tenant_id (from DB, NOT from JWT)
  - Rate-limit dep (si aplica)
   │
   ▼
AuthService.create(tenant_id=tenant_id, actor=user, ...)
  - enforce role rules
  - insert into DB (tenant-scoped)
  - raise ServiceError en errores de dominio
   │
   ▼
Route serializa a UserResponse → FastAPI aplica schema → JSON
```

## Seguridad en la arquitectura

- **Tenant isolation**: el `tenant_id` jamás se lee de query/body. Siempre viene del `CurrentUser` autenticado. Cada ORM query sobre tablas tenant-scoped filtra por `tenant_id`.
- **Sin trust en JWT claims**: el JWT solo contiene `sub`, `jti`, `type`, `mfa_verified`, `exp`. El rol y tenant se leen de la DB cada request.
- **HTTPException solo en `api/`**: services lanzan excepciones de dominio; los controllers mapean. Evita que lógica de negocio dependa del transporte HTTP.

## Tenant isolation

```python
# app/core/tenant.py
async def _get_current_tenant_id(user: CurrentUser) -> uuid.UUID:
    return user.tenant_id

CurrentTenantId = Annotated[uuid.UUID, Depends(_get_current_tenant_id)]
```

Cada service method acepta `tenant_id` como kwarg explícito y filtra queries. Routes lo pasan desde `CurrentTenantId`. Nunca del body/query.

## Estructura del proyecto

```
erp-backend/
├── .claude/                        # Skills + agents del workspace (team config)
│   ├── agents/                     # security-auditor, security-scanner, architecture-reviewer
│   └── skills/                     # secure-coding, clean-architecture
├── .docker/
│   ├── Dockerfile                  # Imagen producción (multi-stage)
│   ├── Dockerfile.dev              # Imagen desarrollo (hot-reload)
│   ├── compose.yml                 # Compose dev (postgres + redis + migrate + api + worker)
│   └── compose.prod.yml            # Compose prod
├── .github/workflows/ci.yml        # Pipeline CI (lint + test + security scans)
├── alembic/                        # Migraciones de DB
├── app/
│   ├── api/v1/                     # Controllers HTTP (routers)
│   │   ├── auth.py, users.py, rooms.py, tags.py, split_configs.py,
│   │   ├── technical_sheets.py, bio_templates.py, shifts.py,
│   │   ├── shift_reports.py, macros.py, salary_advance_requests.py,
│   │   ├── liquidations.py, monitor_salaries.py, metrics.py,
│   │   ├── exchange_rates.py, notifications.py, chat.py,
│   │   ├── exports.py, extension.py, api_keys.py, health.py
│   │   └── router.py               # Agregador
│   ├── core/                       # Cross-cutting
│   │   ├── dependencies.py         # CurrentUser, require_roles, MFAVerifiedUser
│   │   ├── api_key_auth.py         # CurrentApiKeyUser (extensión)
│   │   ├── middleware.py           # SecurityHeadersMiddleware
│   │   ├── rate_limit.py           # RateLimitByIP / ByUser
│   │   ├── security.py             # Password hashing, JWT
│   │   ├── tenant.py               # CurrentTenantId
│   │   ├── html_sanitizer.py       # bleach + CSS sanitizer
│   │   ├── pagination.py           # OffsetPage / CursorPage
│   │   └── ws_hub.py               # Fan-out WebSocket hub
│   ├── models/                     # SQLAlchemy ORM
│   ├── schemas/                    # Pydantic DTOs
│   ├── services/                   # Reglas de negocio (una por agregado)
│   │   └── errors.py               # ServiceError hierarchy
│   ├── workers/                    # Jobs ARQ (Playwright, scrapers)
│   ├── config.py                   # Settings (pydantic-settings, JWT_SECRET obligatorio)
│   ├── database.py
│   ├── redis.py
│   └── main.py                     # FastAPI factory + middlewares
├── docs/                           # Esta carpeta
├── tests/
│   ├── api/                        # Tests de integración por resource
│   └── conftest.py                 # Fixtures (TestingSession, owner_client_a, etc.)
├── .env.example
├── .env.production.example
├── .secrets.baseline               # Baseline de detect-secrets
├── Makefile
├── pyproject.toml
├── poetry.lock
└── ruff.toml
```

## Decisiones de diseño notables

1. **Minimal JWT payload**: rol y tenant NO están en el JWT. El backend siempre los lee de DB; el front los obtiene de `GET /auth/me`. Evita que un claim stale escale privilegios.
2. **Audit log en sesión independiente**: eventos de failure path (login fallido, etc.) se commitean aparte del request transaccional principal, para que sobrevivan al rollback.
3. **ShiftReport auto-generado**: `ShiftService.update()` dispara `ShiftReportService.generate_if_missing()` cuando el status pasa a FINISHED. Idempotente.
4. **API keys para extensión**: separadas del JWT. Argon2-hasheadas con prefix indexado. El plaintext solo se retorna en creación.
5. **WebSocket hub in-process**: MVP fan-out por `(tenant_id, shift_id)` en memoria. Cambiar a Redis pub/sub si se despliega multi-worker.
6. **Pagination dual**: offset para CRUDs (cap 5000 contra DoS), cursor para time-series (O(1), sin COUNT). Ver [`docs/pagination.md`](pagination.md).
