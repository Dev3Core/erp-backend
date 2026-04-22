# Configuration

Todas las variables se validan al boot con `pydantic-settings`. Si falta una obligatoria o un valor es inválido, la app **falla al arrancar** — no hay defaults inseguros.

## Desarrollo (`.env`)

Copiar de `.env.example` y ajustar.

| Variable                      | Obligatoria | Descripción                                                                           | Default                                                             |
|-------------------------------|:-----------:|---------------------------------------------------------------------------------------|---------------------------------------------------------------------|
| `DATABASE_URL`                | No          | String de conexión a PostgreSQL (driver `asyncpg`)                                    | `postgresql+asyncpg://erp:erp_local@localhost:5432/erp_webcam`      |
| `REDIS_URL`                   | No          | String de conexión a Redis                                                            | `redis://localhost:6379`                                            |
| `JWT_SECRET`                  | **Sí**      | Clave HS256. `len >= 64`. Rechaza valores placeholder (`change-me`, prefijo `secret`) | —                                                                   |
| `JWT_ALGORITHM`               | No          | Algoritmo JWT                                                                         | `HS256`                                                             |
| `JWT_EXPIRES_MINUTES`         | No          | TTL access token (min)                                                                | `15`                                                                |
| `JWT_REFRESH_EXPIRES_MINUTES` | No          | TTL refresh token (min)                                                               | `10080` (7 días)                                                    |
| `CORS_ORIGINS`                | No          | Orígenes permitidos (lista JSON)                                                      | `["http://localhost:3000"]`                                         |
| `SESSION_COOKIE_SECURE`       | No          | Flag `Secure` en cookies de sesión. Debe ser `true` en producción (HTTPS)            | `false`                                                             |
| `DEBUG`                       | No          | Modo debug de FastAPI                                                                 | `false`                                                             |

### Generar un `JWT_SECRET`

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Pegarlo en `.env`. La app falla con mensaje claro si el valor es menor a 64 chars o contiene `change-me`.

## Producción (`.env.production`)

Hereda todo lo anterior. Variables adicionales que **solo se usan en el compose de producción**:

| Variable            | Descripción                              |
|---------------------|------------------------------------------|
| `POSTGRES_USER`     | Usuario de PostgreSQL                    |
| `POSTGRES_PASSWORD` | Password de PostgreSQL                   |
| `POSTGRES_DB`       | Nombre de la base de datos               |
| `REDIS_PASSWORD`    | Password de Redis                        |
| `API_PORT`          | Puerto del host donde exponer la API     |

### Obligatorio para prod

- `SESSION_COOKIE_SECURE=true`
- `DEBUG=false`
- `CORS_ORIGINS` con el dominio real del frontend (HTTPS), nunca `*` + credentials.
- `JWT_SECRET` distinto al de dev, generado en el entorno de deploy, jamás en git.

## Dónde viven los valores

| Capa | Mecanismo | Notas |
|------|-----------|-------|
| Desarrollo local | Archivo `.env` | `.gitignore`d. Plantilla en `.env.example` |
| Docker Compose (dev) | `env_file: ../.env` en `compose.yml` | El contenedor `api` hereda las variables del host |
| Docker Compose (prod) | `env_file: ../.env.production` | Distinto archivo, nunca chequear en git |
| CI | Variables de entorno del job `lint-and-test` en `.github/workflows/ci.yml` | Solo `JWT_SECRET` dummy para que la app bootee; DBs son containers de servicio |
| Deploy real | Secret manager (Docker secrets, K8s secrets, Vault, etc.) | Nunca hardcodear ni meter en images |

## Secretos que NUNCA deben estar en git

- `.env`, `.env.production`
- `alembic.ini` con password real (usar env vars)
- Keys privadas, tokens, passwords

`detect-secrets` con `.secrets.baseline` está configurado en CI para bloquear commits con secretos nuevos. Ver [`docs/security.md`](security.md).

## Troubleshooting

**"JWT_SECRET must not be a placeholder"** al arrancar
→ Generar uno real y ponerlo en `.env`.

**"relation users does not exist"** en la primera request
→ Migraciones no corrieron. El servicio `migrate` en `compose.yml` debería correr antes del `api`. Si no, ejecutar manual: `make migrate` (host) o `docker compose -f .docker/compose.yml exec api poetry run alembic upgrade head`.

**Cookies no llegan al backend desde el frontend en prod**
→ Verificar `SESSION_COOKIE_SECURE=true`, HTTPS terminado upstream, y que el dominio del front esté en `CORS_ORIGINS`. Para cross-site (app.ex.com → api.ex.com), las cookies necesitan `SameSite=None; Secure` — hoy están en `Lax`. Ajustar `_COOKIE_OPTS` en `app/api/v1/auth.py` si se necesita.

**TRM falla con 503**
→ `datos.gov.co` inaccesible. Cachear manualmente con `POST /api/v1/exchange-rates` (admin).
