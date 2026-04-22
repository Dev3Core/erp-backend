# API Reference

> Source of truth while the server is running: **Swagger UI at `/docs`**, ReDoc at `/redoc`. This doc is a hand-written catalog for when the server isn't up.

All endpoints live under `/api/v1`. Responses are JSON unless noted (exports return binary).

## Authentication

Two mechanisms:

- **Cookie JWT** (web clients): `access_token` + `refresh_token` HttpOnly cookies set by `POST /auth/login`. Frontend calls `GET /auth/me` to obtain user info.
- **API key** (Chrome extension): short-lived key issued by `POST /auth/api-keys`. Sent as `X-API-Key: <plaintext>` or `Authorization: Bearer <plaintext>`. Only unlocks `/ext/*` endpoints.

---

## `/api/v1/auth`

| Método | Ruta             | Descripción                                                                 | Auth    | Rate limit     |
|--------|------------------|-----------------------------------------------------------------------------|---------|----------------|
| POST   | `/register`      | Crea tenant + owner. Retorna IDs y slug                                     | Público | 3 / min / IP   |
| POST   | `/login`         | Login; setea `access_token` + `refresh_token` cookies                       | Público | 5 / min / IP   |
| POST   | `/refresh`       | Rota access + refresh, blacklistea el anterior                              | Cookie  | —              |
| POST   | `/logout`        | Invalida tokens en Redis (blacklist)                                        | Cookie  | —              |
| GET    | `/me`            | Datos de sesión (rol, tenant, slug, flags)                                  | JWT     | —              |
| POST   | `/mfa/setup`     | Genera secreto TOTP + `otpauth://` URI                                      | JWT     | —              |
| POST   | `/mfa/verify`    | Valida código TOTP; activa MFA en primer verify                             | JWT     | 5 / min / user |
| POST   | `/api-keys`      | Emite API key efímera (extensión Chrome). Plaintext retornado una sola vez  | JWT     | —              |
| GET    | `/api-keys`      | Lista las keys del usuario actual                                           | JWT     | —              |
| DELETE | `/api-keys/{id}` | Revoca una key propia                                                       | JWT     | —              |

## Recursos tenant-scoped

Todos expuestos bajo `/api/v1/<resource>`. OWNER/ADMIN escriben; reads varían por rol (ver Swagger).

| Ruta                               | Descripción                                                                                   |
|------------------------------------|-----------------------------------------------------------------------------------------------|
| `POST/GET/PATCH/DELETE /users`     | Gestiona usuarios del estudio (MONITOR/MODEL). OWNER no asignable; solo OWNER promueve a ADMIN |
| `POST/GET/PATCH/DELETE /rooms`     | Cuentas de Chaturbate/Stripchat (soft delete, unique por plataforma+url)                      |
| `POST/GET/PATCH/DELETE /tags`      | Tags por room/plataforma (scraper pendiente)                                                  |
| `POST/GET/PATCH/DELETE /split-configs` | % platform/studio/model (suma 100, un default por tenant)                                 |
| `POST/GET/PATCH/DELETE /technical-sheets` | Ficha de modelo (bio, idiomas, categorías, notas)                                      |
| `POST/GET/PATCH/DELETE /bio-templates` | Plantillas HTML con sanitizer (bleach)                                                    |
| `POST/sanitize` → `/bio-templates/sanitize` | Sanitiza HTML al vuelo (preview sin persistir)                                        |
| `POST/GET/PATCH/DELETE /shifts`    | Turnos (model + room + monitor opcional + tiempos)                                            |
| `GET /shift-reports`               | Resumen auto-generado al finalizar un shift                                                   |
| `GET /shift-reports/by-shift/{id}` | Reporte de un shift específico                                                                |
| `POST/GET/PATCH/DELETE /macros`    | Quick-replies por usuario (sincronizados con la extensión)                                    |

## Liquidaciones y sueldos

| Método / Ruta                              | Descripción                                                                           |
|--------------------------------------------|---------------------------------------------------------------------------------------|
| `POST /liquidations/from-shift`            | Crea liquidación desde shift FINISHED: aplica split, convierte USD→COP con TRM       |
| `GET /liquidations`                        | Lista (cursor) con filtros por status, rango de fechas, shift_id                     |
| `PATCH /liquidations/{id}`                 | Transición de estado: PENDING → APPROVED → PAID (y APPROVED ↔ PENDING)                |
| `DELETE /liquidations/{id}`                | Elimina (bloqueado si PAID)                                                           |
| `POST/GET/DELETE /monitor-salaries`        | Historial de sueldos por monitor (append-only)                                       |
| `GET /monitor-salaries/current/{monitor_id}` | Sueldo vigente en una fecha (`?as_of=YYYY-MM-DD`)                                   |
| `POST /salary-advances`                    | Cualquier usuario puede solicitar                                                     |
| `GET /salary-advances/mine`                | Solicitudes del usuario actual                                                        |
| `GET /salary-advances`                     | Lista para OWNER/ADMIN (filtrable por status)                                         |
| `PATCH /salary-advances/{id}/review`       | OWNER/ADMIN aprueba/rechaza/paga                                                      |

## Métricas (owner dashboard)

| Método / Ruta                         | Descripción                                                         |
|---------------------------------------|---------------------------------------------------------------------|
| `GET /metrics/overview`               | Totales de shifts/tokens/USD y conteo de liquidaciones por status   |
| `GET /metrics/revenue-by-model`       | Ranking de modelos por USD generado                                 |
| `GET /metrics/revenue-by-monitor`     | Ranking de monitores (vía shifts asignados)                         |
| `GET /metrics/revenue-by-platform`    | Chaturbate vs Stripchat                                             |
| `GET /metrics/daily-revenue`          | Serie temporal diaria (rango obligatorio)                           |
| `GET /metrics/model/overview`         | Endpoint self-service para rol MODEL                                |
| `GET /metrics/model/best-monitor`     | Mejor monitor estadísticamente para la modelo autenticada           |

## TRM / Tasa de cambio

| Método / Ruta                  | Descripción                                                |
|--------------------------------|------------------------------------------------------------|
| `GET /exchange-rates/today`    | TRM vigente hoy (cache-aside contra datos.gov.co)          |
| `GET /exchange-rates/{date}`   | TRM para una fecha específica                              |
| `POST /exchange-rates`         | Override manual (admin/owner)                              |

## Notificaciones

| Método / Ruta                        | Descripción                                                |
|--------------------------------------|------------------------------------------------------------|
| `GET /notifications`                 | Lista (cursor) con filtro `?unread_only=true`              |
| `GET /notifications/unread-count`    | Counter para badge (`{unread_count: N}`)                   |
| `POST /notifications/mark-read`      | Marca leídas por ids                                        |
| `POST /notifications/mark-all-read`  | Marca todas leídas                                         |

## Chat

| Método / Ruta                          | Descripción                                                           |
|----------------------------------------|-----------------------------------------------------------------------|
| `GET /chat/shift/{id}/messages`        | Lista (cursor). Participantes: model, monitor, OWNER, ADMIN           |
| `POST /chat/shift/{id}/messages`       | Enviar mensaje (fan-out vía WebSocket hub)                            |
| `WS /chat/shift/{id}/ws`               | Conexión bidireccional; auth vía cookie `access_token`                |

## Exports

| Método / Ruta                           | Descripción                                                     |
|-----------------------------------------|-----------------------------------------------------------------|
| `GET /exports/liquidations.csv`         | Dump CSV (hasta 10k filas)                                      |
| `GET /exports/liquidations.pdf`         | PDF con ReportLab                                               |

## Extensión Chrome (`/ext/*`)

Autenticado con API key (header `X-API-Key` o `Authorization: Bearer`).

| Método / Ruta          | Descripción                                           |
|------------------------|-------------------------------------------------------|
| `GET /ext/me`          | Identidad mínima (id, email, tenant)                 |
| `GET /ext/macros`      | Quick-replies activos para el usuario                |

## Health

| Método | Ruta        | Descripción     | Auth    |
|--------|-------------|-----------------|---------|
| GET    | `/health`   | Health check    | Público |

---

## Paginación

Ver [`docs/pagination.md`](pagination.md). Resumen:

- **Offset** — CRUDs bounded. Query: `limit`, `offset` (cap `offset + limit <= 5000`). Shape: `{items, total, limit, offset, has_next, has_prev}`.
- **Cursor** — time-series (shifts, reports, liquidations, notifications, chat). Query: `cursor`, `limit`. Shape: `{items, next_cursor, prev_cursor, limit}`.

## Códigos de estado comunes

- `200 OK` — lectura/actualización exitosa
- `201 Created` — creación exitosa
- `204 No Content` — delete exitoso
- `400 Bad Request` — input mal formado
- `401 Unauthorized` — sin cookie/API key o inválida
- `403 Forbidden` — sin permisos (rol insuficiente o no-participante)
- `404 Not Found` — recurso no existe o no pertenece al tenant
- `409 Conflict` — duplicate (email, room url, etc.)
- `422 Unprocessable Entity` — validación Pydantic, transición inválida, offset fuera de cap, cursor corrupto
- `429 Too Many Requests` — rate limit (header `Retry-After`)
- `503 Service Unavailable` — TRM upstream inaccesible y sin cache
