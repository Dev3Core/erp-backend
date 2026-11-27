# Architecture

## Monolito modular

Un solo desplegable (una app FastAPI, un worker arq, una base PostgreSQL), con el
código organizado en **módulos verticales por dominio** cuyos límites se verifican
automáticamente con [import-linter](https://import-linter.readthedocs.io/)
(`make lint-arch`, también en CI).

```
app/
├── main.py              # FastAPI factory + middlewares (composition root)
├── routes.py            # Agrega los routers de cada módulo bajo /api/v1 (composition root)
├── models_registry.py   # Importa los modelos de todos los módulos (Base.metadata completo)
├── config.py            # Settings (pydantic-settings)
├── workers/tasks.py     # Shim: `arq app.workers.tasks.WorkerSettings` → modules.automation
├── shared/              # Infraestructura transversal, SIN lógica de dominio
│   ├── database.py      # engine, async_session, get_db
│   ├── orm.py           # Base, TimestampMixin, TenantMixin (un solo Base para todo)
│   ├── redis.py · security.py (JWT/argon2) · pagination.py · rate_limit.py (por IP)
│   ├── middleware.py · html_sanitizer.py · ws_hub.py
│   └── errors.py        # ServiceError, NotFoundError, ForbiddenError, ConflictError, ValidationError
└── modules/
    ├── identity/        # auth, usuarios, MFA, API keys, tenant, audit log
    ├── studio/          # rooms, tags, fichas técnicas, bio templates, macros
    ├── shifts/          # turnos, reportes de turno, chat (REST + WS)
    ├── payroll/         # splits, TRM, liquidaciones, salarios de monitores, adelantos
    ├── insights/        # métricas y exports (CSV/PDF), solo lectura
    ├── notifications/   # notificaciones in-app
    ├── extension/       # endpoints /ext/* (API key)
    ├── automation/      # modelo AutomationJob + tareas arq (placeholder)
    └── health/          # /health
```

Estructura interna de cada módulo (los que tienen varios agregados usan paquetes):

```
modules/<m>/
├── __init__.py              # API PÚBLICA del módulo
├── router.py | routers/     # Controllers finos: parsear -> llamar servicio -> formar respuesta
├── dependencies.py          # (opcional) dependencias FastAPI propias del módulo
├── service.py | services/   # Reglas de negocio, transacciones, orquestación
├── schemas.py | schemas/    # Pydantic (contratos I/O)
└── models.py | models/      # ORM (datos), registrado en el Base de app.shared.orm
```

## Reglas de dependencia

1. **`app.shared` no importa `app.modules`** (ni `app.main`, `app.routes`, `app.models_registry`).
2. **API pública**: un módulo solo puede importar otro módulo por su paquete raíz
   (`from app.modules.identity import CurrentUser`), nunca sus internals
   (`app.modules.identity.models.user`, `...services.auth`, etc.). El `__init__.py` reexporta
   exclusivamente lo que otros módulos pueden usar.
3. **Dependencias entre módulos explícitas**: además de pasar por la raíz, cada arista
   módulo → módulo debe estar declarada en `ignore_imports` del contrato `independence` en
   `pyproject.toml`. Una dependencia nueva (o un ciclo) rompe `lint-imports` hasta que se
   declare y se documente aquí.
4. **Capas dentro del módulo**: `router(s) → dependencies → service(s) → schemas → models`.
   Los imports solo van hacia abajo. `HTTPException` solo se levanta en routers/dependencies;
   los servicios lanzan `ServiceError` y subclases que los routers mapean.
5. `app/main.py`, `app/routes.py` y `app/models_registry.py` son la *composition root*: pueden
   importar la API pública de todos los módulos. Los tests son caja blanca y pueden importar
   internals.

Detalle de anti-patrones: [`.claude/skills/clean-architecture/SKILL.md`](../.claude/skills/clean-architecture/SKILL.md).

## Dependencias permitidas entre módulos

Grafo acíclico. `automation` y `health` no dependen de ningún módulo; nadie depende de
`insights` ni de `extension`.

| Desde | Hacia | Qué usa (API pública) | Tipo |
|-------|-------|-----------------------|------|
| studio, shifts, payroll, insights, notifications, extension | identity | `CurrentUser`, `CurrentTenantId`, `require_roles`, `Role`, `User` (tipado y checks de rol); extension: `CurrentApiKeyUser` | API pública |
| studio (`technical_sheet`) | identity | `user_has_role_in_tenant` (valida que el modelo sea MODEL del tenant) | API pública |
| shifts (`shift`) | identity | `user_has_role_in_tenant(..., active_only=True)` (modelo/monitor activos) | API pública |
| payroll (`monitor_salary`) | identity | `user_has_role_in_tenant` (MONITOR del tenant) | API pública |
| insights (`exports`) | identity | `get_tenant_name` (nombre del estudio en el PDF) | API pública |
| shifts (`shift`) | studio | `room_is_active_in_tenant` | API pública |
| extension | studio | `MacroService`, `MacroResponse`, `Platform` | API pública |
| payroll (`liquidation`) | shifts | `get_shift_in_tenant`, `Shift` (lee estado y `usd_earned` del turno) | API pública |
| insights (`exports`) | payroll | `LiquidationService`, `ExchangeRateService`, `get_exchange_rate_service`, `LiquidationStatus` | API pública |
| insights (`metrics`) | identity, studio, shifts, payroll | `User`, `Room`, `Shift`/`ShiftStatus`, `Liquidation`/`LiquidationStatus` | **ORM de solo lectura permitido** |

**ORM de solo lectura**: `insights.metrics` hace agregados (`JOIN` + `GROUP BY`) sobre tablas de
varios módulos. Pasar por servicios obligaría a traer filas a memoria, así que los dueños
reexportan esos modelos en su `__init__` como dependencia explícita y aceptada. Regla: insights
**solo lee**; nunca crea, modifica ni borra filas de otro módulo.

**Relaciones ORM entre módulos** (`User.shifts`, `Shift.liquidation`, `Room.shifts`, `Tenant.rooms`,
FKs a `tenants.id`/`users.id`, etc.) se declaran con targets en string y no generan imports;
se resuelven porque `app/models_registry.py` carga todos los modelos sobre el mismo `Base`
(lo importan `app/main.py` y `alembic/env.py`).

**Sin bus de eventos**: hoy ningún efecto secundario cruza módulos en sentido contrario al grafo
(p. ej. payroll no crea notificaciones), así que no hay ciclos que romper. Si aparece uno
(p. ej. "adelanto aprobado → notificar" y notifications necesitara leer payroll), introducir
`app/shared/events.py` (eventos síncronos como dataclasses, suscripción en el arranque) en vez
de una importación circular.

### Por qué las dependencias de auth viven en identity y no en `shared`

`CurrentUser`, `require_roles`, `require_mfa`, `CurrentTenantId`, `CurrentApiKeyUser` y
`RateLimitByUser` cargan la fila `User` y verifican API keys con `ApiKeyService`, que son de
identity. Ponerlas en `shared` violaría la regla 1, así que están en
`app/modules/identity/dependencies.py` y se exponen por `app.modules.identity`. `shared` conserva
las primitivas sin dominio: JWT/argon2 (`security.py`) y el rate-limit por IP (`rate_limit.py`).

## Cómo añadir un módulo nuevo

1. Crear `app/modules/<nuevo>/` con `__init__.py`, `router.py`, `service.py`, `schemas.py`,
   `models.py` (o paquetes `routers/`, `services/`, ... si hay varios agregados).
2. Modelos: heredar de `app.shared.orm.Base` (+ `TenantMixin`/`TimestampMixin`); relaciones hacia
   otros módulos con target string (`relationship("User")`, `ForeignKey("users.id")`).
3. Registrar los modelos en `app/models_registry.py` y generar la migración
   (`make migration msg="..."`).
4. En `__init__.py` reexportar solo lo que otros módulos pueden usar (router, funciones de
   servicio, DTOs) y declarar `__all__`.
5. Incluir el router en `app/routes.py`.
6. Añadir el módulo a `modules` (contrato `independence`) y a `containers` (contrato `layers`)
   en `pyproject.toml`; declarar en `ignore_imports` cada dependencia hacia otro módulo
   (`"app.modules.<nuevo>.** -> app.modules.identity"`) y documentarla en la tabla de arriba.
7. `make lint-arch && make lint && make test`.

## Patrones aplicados

| Patrón | Dónde | Por qué |
|--------|-------|---------|
| Dependency Injection vía FastAPI `Depends` | `CurrentUser`, `CurrentTenantId`, service factories, pagination params | Testabilidad + override en tests |
| Service layer | `app/modules/<m>/service(s)` | Reglas de negocio fuera de routes, reusables |
| Repository-lite | Queries viven en el service del módulo que owna el aggregate | Evita queries esparcidas |
| Unit of Work = 1 request = 1 session | `get_db` dependency | Transacciones atómicas por request |
| Independent session para audit | `AuthService._audit()` | Logs de failure path sobreviven al rollback principal |
| Domain errors | `app/shared/errors.py` | `NotFoundError`, `ForbiddenError`, `ConflictError`, `ValidationError`, `ServiceError` base |
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
- **HTTPException solo en routers**: services lanzan excepciones de dominio; los controllers mapean. Evita que lógica de negocio dependa del transporte HTTP.

## Tenant isolation

```python
# app/modules/identity/dependencies.py
async def _get_current_tenant_id(user: CurrentUser) -> uuid.UUID:
    return user.tenant_id

CurrentTenantId = Annotated[uuid.UUID, Depends(_get_current_tenant_id)]
```

Cada service method acepta `tenant_id` como kwarg explícito y filtra queries. Routes lo pasan desde `CurrentTenantId`. Nunca del body/query.

## Estructura del proyecto

```
erp-backend/
├── .claude/                        # Skills + agents del workspace (team config)
├── .docker/                        # Dockerfile(s) + compose dev/prod (api + worker arq)
├── .github/workflows/ci.yml        # Pipeline CI (lint + lint-arch + test + security scans)
├── alembic/                        # Migraciones (env.py importa app.models_registry)
├── app/                            # Ver "Monolito modular" arriba
├── docs/                           # Esta carpeta
├── tests/
│   ├── api/                        # Tests de integración por resource
│   └── conftest.py                 # Fixtures (TestingSession, owner_client_a, etc.)
├── Makefile                        # make lint-arch = poetry run lint-imports
├── pyproject.toml                  # Dependencias + contratos [tool.importlinter]
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
