# Security

Enfoque: OWASP Top 10 como requisito no negociable, defensa en profundidad, y *fail closed* en cada capa.

## Controles activos

| Capa              | Control                                                                                                                                 |
|-------------------|-----------------------------------------------------------------------------------------------------------------------------------------|
| Transport         | HSTS (`max-age=63072000; includeSubDomains`), cookies `Secure` en prod (flag env-driven), CORS con allowlist explícita (no `*`)         |
| Headers           | CSP `default-src 'self'; frame-ancestors 'none'` (relajada solo en `/docs` para Swagger), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, COOP, CORP, `Permissions-Policy` |
| Autenticación     | argon2 para passwords; JWT firmado HS256 con **payload mínimo** (solo `sub`, `jti`, `type`, `mfa_verified`, `exp`); rol y tenant siempre desde DB; rotación de refresh token; blacklist en Redis por `jti` |
| Sesiones          | Cookies `HttpOnly` + `SameSite=Lax` + `Secure` (prod). El frontend no puede leer el JWT desde JS.                                        |
| API keys          | Emitidas por usuario para la extensión Chrome. Argon2-hasheadas. Prefix indexado para lookup. TTL máximo 168h. Revocables.              |
| MFA               | TOTP (pyotp). `setup` + `verify` separados. Verificación obligatoria para acciones sensibles (`MFAVerifiedUser` dep)                    |
| Rate limiting     | Redis `INCR`+`EXPIRE` por IP o user en endpoints críticos (`/auth/login` 5/min/IP, `/auth/register` 3/min/IP, `/auth/mfa/verify` 5/min/user). Responde 429 + `Retry-After` |
| Tenant isolation  | `tenant_id` jamás del query/body — siempre del `CurrentUser` autenticado. Cada ORM query sobre tablas tenant-scoped filtra por `tenant_id`. Tests explícitos de cross-tenant. |
| Validación input  | Pydantic v2 en todo body. `EmailStr`, `SecretStr`, `constr(min_length=...)`, `UUID4`, `extra="forbid"` en schemas sensibles              |
| SQLi              | SQLAlchemy 2.0 expressions exclusivamente; prohibido `text()` con interpolación. Cero uso de raw SQL                                    |
| XSS (bio)         | `bleach[css]` con allowlist de tags/atributos/CSS + endpoint `/bio-templates/sanitize` para preview                                     |
| Output            | Nunca se exponen tracebacks, SQL, o exception messages al cliente. Solo `HTTPException` con `detail` controlado                         |
| Secrets           | Exclusivamente vía `pydantic-settings`. `.env*` en `.gitignore`. `detect-secrets` con baseline en CI. `JWT_SECRET` rechaza placeholders |
| Audit trail       | `AuditLog` por evento auth (register, login success/failure/blocked, logout, MFA setup/verify success/failure). Sesión independiente para sobrevivir rollback |
| SSRF              | `ExchangeRateService` con allowlist explícita de host (`www.datos.gov.co`). Outbound HTTP solo via `httpx` con timeout                  |
| Dependencias      | pip-audit en CI. Dependabot activo. CVEs se patchean en PRs dedicados                                                                    |

## OWASP Top 10 (2021) mapeo

| # | Riesgo | Cómo lo cubrimos |
|---|--------|------------------|
| A01 | Broken Access Control | RBAC estricto (`require_roles`), tenant isolation via `CurrentTenantId` + filtros ORM; tests explícitos cross-tenant |
| A02 | Cryptographic Failures | argon2 (passwords), JWT HS256 con `JWT_SECRET` validado >= 64 chars, TLS upstream |
| A03 | Injection | SQLAlchemy expressions; Pydantic en todo input; bleach en bios |
| A04 | Insecure Design | Capas limpias, servicios con reglas de negocio separadas de transport, domain errors |
| A05 | Security Misconfiguration | Security headers middleware, CORS allowlist, `DEBUG=false` prod, Docker non-root + read-only FS |
| A06 | Vulnerable Components | pip-audit en CI + Dependabot, versiones pineadas en `poetry.lock` |
| A07 | Auth Failures | MFA TOTP, refresh rotation, blacklist Redis, lockout por rate-limit, cookies HttpOnly |
| A08 | Data Integrity | Migraciones Alembic reviewed, no `eval`/`pickle` de input no confiable, commits opcionalmente firmados |
| A09 | Logging Failures | `AuditLog` en eventos auth, structured logging, sesión independiente para no perder trazas en rollback |
| A10 | SSRF | Outbound HTTP con host allowlist (`datos.gov.co`), timeout estricto en `httpx` |

## Herramientas automáticas

| Tipo      | Herramienta       | Target                                                   |
|-----------|-------------------|----------------------------------------------------------|
| SAST      | bandit            | `app/` — vulnerabilidades Python comunes                 |
| SAST      | ruff `--select S` | reglas bandit embebidas en ruff (rápido, local)          |
| SAST      | semgrep           | packs `p/owasp-top-ten`, `p/python`, `p/security-audit`  |
| SCA       | pip-audit         | CVEs en dependencias (skip editable self-package)        |
| Secrets   | detect-secrets    | secretos hardcodeados; baseline versionada               |

### Comandos

```bash
make sast            # bandit + ruff-S
make sca             # pip-audit
make secrets-scan    # detect-secrets vs baseline
make semgrep-scan    # semgrep OWASP + python + security-audit
make security-scan   # corre los 4 anteriores en secuencia
```

### Actualizar baseline de secrets

Cuando se acepta un placeholder nuevo (ej. en un ejemplo de doc):

```bash
poetry run detect-secrets scan > .secrets.baseline
make secrets-audit    # auditoría interactiva para marcar falsos positivos
```

## CI/CD

Cada PR contra `main` ejecuta en paralelo:

1. `lint-and-test` — `ruff check`, `ruff format --check`, `pytest -v`.
2. `security-scan` — los 4 scanners de arriba.

Ambos deben pasar. Configuración en [.github/workflows/ci.yml](../.github/workflows/ci.yml).

## Agents de seguridad en el workspace

Para el desarrollo asistido con Claude, hay agents dedicados en `.claude/agents/`:

- **`security-auditor`** — revisa el diff contra OWASP Top 10 manualmente. Reporta findings, no edita.
- **`security-scanner`** — corre los scanners automáticos, triage, reporte. No edita.
- **`architecture-reviewer`** — chequea SOLID, ciclos de import, breaches de capa. No edita.

Invocar con `Agent` tool antes de abrir PRs que toquen auth/security-sensitive code.

## Reporte de vulnerabilidades

**No reportar por issues públicos.** Abrir un advisory privado en [GitHub Security Advisories](https://github.com/Dev3Core/erp-backend/security/advisories/new) con:

- Descripción del issue
- Pasos de reproducción
- Impacto estimado
- Versión / commit afectado

Respuesta target: 48h.

## Conocidas limitaciones

- **ecdsa (GHSA-wj6h-64fc-37mp)**: timing attack en P-256. No explotable aquí porque se firma con HS256, no ECDSA. Upstream no va a arreglar. Se dismisseó el alert con justificación. TODO: migrar `python-jose` → `pyjwt` para evitar la dependencia.
- **WebSocket hub in-process**: el chat fan-out es por proceso. En multi-worker hay que cambiar a Redis pub/sub antes de escalar horizontalmente.
- **Cursor prev navigation**: la navegación hacia atrás en cursor pagination está implementada pero con edge cases cuando hay muchos timestamps idénticos. Forward navigation es el flujo primario y está testeado.
