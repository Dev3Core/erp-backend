---
name: clean-architecture
description: Enforces SOLID, layered architecture (api → services → models), zero circular imports, and correct choice between OOP and functional style for this FastAPI backend. Use on any change to app/api, app/services, app/core, app/models, app/schemas — especially when adding new modules, refactors, abstractions, or cross-module imports.
---

# Clean Architecture — SOLID + Layers

## Layer rule (prevents circular imports)

```
app/api/v1/*      (thin controllers: parse → call service → shape response)
   ↓
app/services/*    (business rules, transactions, orchestration)
   ↓
app/core/*        (security, deps, tenant, cross-cutting)
   ↓
app/models/*      (SQLAlchemy ORM — data only)
app/schemas/*     (Pydantic — I/O contracts only)
app/config.py · app/database.py · app/redis.py   (infrastructure)
```

Import direction is **top-down only**. A lower layer never imports a higher one.

- `models/` must not import from `services/`, `api/`, `schemas/`.
- `schemas/` must not import from `models/`, `services/`, `api/`. It is pure I/O contract.
- `services/` may import `models`, `schemas`, `core`, `config`, infra. Never `api/`.
- `api/` may import everything below. Never import from another `api/*` module except the router registry.
- `core/` may import `models`, `config`, infra. Never `services/` or `api/`.

If two modules in the same layer need each other, one of them is doing the wrong job — split or move the shared piece down a layer.

## Breaking a cycle

1. Move the shared type/protocol to a lower layer (often `core/` or a new `app/domain/` for pure dataclasses).
2. Use `from __future__ import annotations` + `TYPE_CHECKING` for type-only imports — never for runtime.
3. Invert dependency: pass the collaborator in via constructor (DI) instead of importing it.

## SOLID in this codebase

- **S — Single Responsibility**: one class/function, one reason to change. Auth, MFA, tokens, audit — separate methods on `AuthService` or separate services. Routes do I/O shaping only.
- **O — Open/Closed**: extend via new strategy/service, not by editing a growing `if/elif` block. Enums + dispatch dict over chained conditionals.
- **L — Liskov**: subclasses keep the parent contract. If you'd need to check `isinstance` to know which is which, it's not a real subtype — use composition.
- **I — Interface Segregation**: narrow `Protocol`s. A service that only needs `.get(id)` takes a `UserReader` protocol, not the full `AuthService`.
- **D — Dependency Inversion**: depend on protocols/abstractions at module boundaries. FastAPI `Depends` is the DI mechanism — wire concretes there, not inside functions.

## OOP vs Functional — when to use which

| Use OOP (class) | Use functional (module-level fn) |
|---|---|
| Holds state across calls (db session, redis, cache) | Pure transformation of input → output |
| Coordinates multi-step transactions | Single-purpose helper, no state |
| Polymorphism / strategy / replaceable implementation | Pipeline-like data shaping (map/filter/reduce) |
| Lifecycle (open/close, setup/teardown) | Validators, parsers, calculators |

**Defaults for this repo:**
- Services = classes (e.g. `AuthService`). Inject deps via `__init__`.
- Security / crypto / token utils = module-level functions (pure or nearly so) — see `app/core/security.py`.
- Pydantic schemas = declarative, no methods beyond validators.
- ORM models = dataclass-like: columns + relationships + trivial helpers only. No business logic.

Prefer small pure functions inside a service method when a step is stateless — easier to test than private methods.

## Patterns already in use (follow them)

- **Dependency Injection via `Annotated[..., Depends(...)]`** — see `CurrentUser`, `AuthServiceDep`. New services get the same treatment.
- **Repository-lite via service methods** — queries live in the service that owns the aggregate. Don't spread queries across routes.
- **Unit of work = one request = one `AsyncSession`** from `get_db`. Don't open your own sessions inside services.
- **Custom domain errors** (`AuthError`) caught in the route and mapped to `HTTPException`. Services don't raise `HTTPException`.
- **Enums (`StrEnum`) over magic strings** — `TokenType`, `Role`.

## Anti-patterns — reject in review

- Business logic in route handlers.
- ORM queries built in `api/` modules.
- `HTTPException` raised from `services/`.
- `from app.api...` inside `services/`, `models/`, `schemas/`, `core/`.
- Deep inheritance (>2 levels) used for code reuse — prefer composition.
- Classes with only `__init__` + one method — that's a function.
- Modules named `utils.py`, `helpers.py`, `common.py` — name by responsibility.
- Premature abstractions for one implementation. Wait for the second caller.

## Checklist before finishing

- [ ] New imports respect layer direction (api→service→core/model; never up)
- [ ] No module imports another module in its own layer except routers
- [ ] Route handler ≤ ~30 lines and does no DB query directly
- [ ] Service receives collaborators via `__init__`, not via module-level globals
- [ ] Public class/function has one clear responsibility
- [ ] Picked OOP vs functional per the table above, not by habit
- [ ] No new `utils.py` / `helpers.py` / `common.py`
