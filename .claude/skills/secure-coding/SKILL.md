---
name: secure-coding
description: Enforces OWASP Top 10 and secure-coding rules for this FastAPI + SQLAlchemy + Redis backend (SQLi, XSS, CSRF, auth/JWT, headers, secrets, tenant isolation, input validation, rate limiting). Use whenever writing or modifying code under app/api, app/services, app/models, app/schemas, app/core, or alembic — and on any auth, session, cookie, crypto, or DB query change.
---

# Secure Coding — OWASP Top 10 (2021)

Apply on every edit to backend code. When in doubt, choose the safer option and flag the tradeoff.

## Non-negotiable rules

1. **No raw SQL with string interpolation.** Use SQLAlchemy Core/ORM expressions: `select(User).where(User.email == email)`. If `text()` is unavoidable, use bound params: `text("... :email").bindparams(email=email)`. Never f-string user input into a query.
2. **Every request schema is a Pydantic model.** No `dict` or `Any` body. Use `EmailStr`, `constr(min_length=...)`, `SecretStr`, `UUID4`. Reject unknown fields: `model_config = ConfigDict(extra="forbid")`.
3. **Tenant isolation is mandatory on every query.** Any query touching a tenant-scoped table must filter by `tenant_id` taken from the authenticated user — never from the request body/query.
4. **Auth state comes from `CurrentUser` / `MFAVerifiedUser`.** Never trust `user_id` from the body. Use `app/core/dependencies.py`.
5. **Passwords: argon2 via `app.core.security.hash_password` / `verify_password`.** No bcrypt, no sha*. Never log or return hashes.
6. **Tokens: JWT via `app.core.security`.** Always check `type` claim matches expected (`ACCESS`/`REFRESH`) and consult the `token_blacklist_key` before trust.
7. **Cookies: `httponly=True`, `samesite="lax"`, `secure=True` in prod.** Follow `_COOKIE_OPTS` in `app/api/v1/auth.py`. Never put tokens in response bodies except where already done.
8. **Secrets only via `app.config.settings`.** No hardcoded keys, passwords, URLs. `.env` stays out of git.
9. **Authorization: least privilege.** Role checks via `require_roles(...)`; MFA-sensitive actions via `MFAVerifiedUser`. Do not hand-roll role checks inline.
10. **Errors: never leak internals.** Raise `HTTPException` with generic detail; log details server-side. Don't echo tracebacks, SQL, or raw exception messages to clients.

## OWASP Top 10 mapping

| # | Risk | Rule in this repo |
|---|------|-------------------|
| A01 | Broken Access Control | Every endpoint declares auth dep + role/MFA dep; tenant filter on every ORM query |
| A02 | Cryptographic Failures | argon2 for passwords; JWT signed with `JWT_SECRET` (`HS256` via config); TLS terminated upstream |
| A03 | Injection | SQLAlchemy expressions only; Pydantic validation on input; HTML/JSON responses via FastAPI serializers |
| A04 | Insecure Design | Services encapsulate business rules; endpoints are thin controllers; no auth logic in routes |
| A05 | Security Misconfiguration | CORS allowlist from `settings.CORS_ORIGINS`; `DEBUG=False` in prod; security headers middleware |
| A06 | Vulnerable Components | Pin versions in `pyproject.toml`; run `poetry audit` / `pip-audit` before release |
| A07 | ID & Auth Failures | MFA via `pyotp`; refresh-token rotation; blacklist on logout; lockout on repeated failures |
| A08 | Software & Data Integrity | Alembic migrations reviewed; no `eval`, no `pickle` on untrusted input |
| A09 | Logging & Monitoring | Audit log via `app/models/audit_log.py` for auth, privilege changes, tenant ops — never log secrets or full tokens |
| A10 | SSRF | Outbound HTTP via `httpx` with strict URL allowlist; never fetch user-supplied URLs without validation |

## Required security headers

Add via middleware (create if missing):

```python
@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    resp.headers["Content-Security-Policy"] = "default-src 'self'"
    resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return resp
```

CORS: `allow_origins=settings.CORS_ORIGINS` (no `["*"]` with `allow_credentials=True` — spec forbids it).

## Rate limiting

State-changing + auth endpoints must be rate-limited. Use `redis` INCR+EXPIRE keyed on IP+route (or user id when authed). Minimum:

- `POST /auth/login` — 5/min per IP
- `POST /auth/register` — 3/min per IP
- `POST /auth/mfa/verify` — 5/min per user

## Checklist before finishing any task

- [ ] All user input passes through a Pydantic schema (`extra="forbid"` on sensitive ones)
- [ ] All ORM queries on tenant tables filter by `tenant_id` from `CurrentUser`
- [ ] Endpoint declares `CurrentUser` / role / MFA deps as needed
- [ ] No raw-SQL string interpolation; no `exec`/`eval`/`pickle` of untrusted data
- [ ] No secret, token, password, or PII in logs or error responses
- [ ] New external HTTP calls validate target host against an allowlist
- [ ] New cookies follow `_COOKIE_OPTS`
- [ ] Rate limit applied to any new auth/mutation endpoint
- [ ] Migration reviewed: no data loss, indexes on `tenant_id` + lookup cols
