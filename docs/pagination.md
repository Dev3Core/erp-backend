# Pagination

All list endpoints in this API use one of two pagination modes. Which mode a
given endpoint uses is fixed and documented in its OpenAPI schema.

---

## Offset pagination (bounded CRUD lists)

**Used for**: `users`, `rooms`, `tags`, `split-configs`, `technical-sheets`,
`bio-templates`, `macros`, `salary-advances`, `auth/api-keys`,
`monitor-salaries`, `ext/macros`.

### Query params

| Param    | Default | Bounds               |
|----------|---------|----------------------|
| `limit`  | 50      | 1 – 200              |
| `offset` | 0       | `offset + limit ≤ 5000` |

Requests that exceed `offset + limit = 5000` are rejected with `422` and a
message pointing to cursor pagination. This cap prevents DoS from deep-offset
scans and forces clients to use cursor pagination for time-series data.

### Response shape

```json
{
  "items": [/* page of objects */],
  "total": 1237,
  "limit": 50,
  "offset": 100,
  "has_next": true,
  "has_prev": true
}
```

`total` is computed with a real `SELECT COUNT(*)`. Fine for CRUD resources
(tenant catalogs, bounded lists). For append-heavy tables, `total` becomes
expensive — those use cursor pagination instead.

### Stable sort

Every list query has `ORDER BY <sort_col> DESC, id DESC` (or equivalent) so
pagination cannot yield duplicates or gaps when two rows share a timestamp.

---

## Cursor pagination (time-series / append-heavy)

**Used for**: `shifts`, `shift-reports`, `liquidations`, `notifications`,
`chat/shift/{id}/messages`.

O(1) per page regardless of depth. No `COUNT(*)`, no offset scan. The cursor
is opaque base64; treat it as a black box on the client.

### Query params

| Param    | Default | Bounds      |
|----------|---------|-------------|
| `cursor` | —       | opaque string; omit for the first page |
| `limit`  | 50      | 1 – 100     |

### Response shape

```json
{
  "items": [/* page of objects */],
  "next_cursor": "eyJ0IjoiMjAyNi0wNC0yMlQxNTozMCIsImkiOiJjMjcuLi4iLCJkIjoibmV4dCJ9",
  "prev_cursor": null,
  "limit": 50
}
```

- `next_cursor` is `null` when you've reached the last page.
- `prev_cursor` is `null` on the first page.
- Clients should loop: request the page, render items, if `next_cursor` is
  non-null pass it back to fetch the next page.

### Cursor contents (informational)

The cursor encodes a JSON object with `{created_at, id, direction}`. The
backend trusts its own cursors cryptographically via the HTTPS transport — it
is NOT signed, so never rely on it for authorization (the tenant filter at
the service layer is what prevents cross-tenant access).

### Stable sort

Cursor pagination always orders by `(created_at DESC, id DESC)` as a stable
tiebreaker. The cursor filter uses:

```
(created_at < cursor_ts) OR (created_at = cursor_ts AND id < cursor_id)
```

so rows with identical timestamps are disambiguated deterministically.

### Notifications unread counter

Notifications use cursor pagination for the list, but the unread badge needs
a quick count. Fetch it via a separate endpoint:

```
GET /api/v1/notifications/unread-count
→ { "unread_count": 12 }
```

---

## Frontend examples

### Offset (Next.js + React)

```ts
const pageSize = 50;
const [page, setPage] = useState(0);

const { data } = useQuery({
  queryKey: ["users", page],
  queryFn: () =>
    fetch(`/api/v1/users?limit=${pageSize}&offset=${page * pageSize}`).then(r => r.json()),
});

// pagination controls
<button disabled={!data?.has_prev} onClick={() => setPage(p => p - 1)}>Prev</button>
<button disabled={!data?.has_next} onClick={() => setPage(p => p + 1)}>Next</button>
<span>Total: {data?.total}</span>
```

### Cursor (infinite scroll)

```ts
const [cursor, setCursor] = useState<string | null>(null);
const [items, setItems] = useState<Shift[]>([]);

async function loadMore() {
  const url = cursor
    ? `/api/v1/shifts?limit=50&cursor=${cursor}`
    : `/api/v1/shifts?limit=50`;
  const data = await fetch(url).then(r => r.json());
  setItems(prev => [...prev, ...data.items]);
  setCursor(data.next_cursor);
}
```

---

## When to add a new paginated endpoint

1. **Is the table bounded** (tens or low hundreds per tenant)? → **offset**.
2. **Is the table append-heavy, grows over time, and you only need recent data by default**? → **cursor**.

Pick one; endpoints do not mix.

### Offset template

```python
from app.core.pagination import (
    OffsetPage, OffsetParams, build_offset_page, count_from, offset_params, paginate_offset,
)

# Service
async def list(self, *, tenant_id, params: OffsetParams, ...):
    stmt = select(X).where(X.tenant_id == tenant_id)...
    stmt = stmt.order_by(X.created_at.desc(), X.id.desc())  # stable
    return await paginate_offset(self._db, stmt=stmt, count_stmt=count_from(stmt), params=params)

# Route
@router.get("", response_model=OffsetPage[XResponse])
async def list_x(
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
    params: Annotated[OffsetParams, Depends(offset_params)],
    ...
):
    items, total = await svc.list(tenant_id=tenant_id, params=params, ...)
    return build_offset_page([XResponse.model_validate(x) for x in items], total, params)
```

### Cursor template

```python
from app.core.pagination import (
    CursorPage, CursorParams, build_cursor_page, cursor_params, paginate_cursor,
)

# Service
async def list(self, *, tenant_id, params: CursorParams, ...):
    stmt = select(X).where(X.tenant_id == tenant_id)...
    return await paginate_cursor(
        self._db, stmt=stmt, params=params,
        created_col=X.created_at, id_col=X.id,
    )

# Route
@router.get("", response_model=CursorPage[XResponse])
async def list_x(
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
    params: Annotated[CursorParams, Depends(cursor_params)],
    ...
):
    items, next_cursor, prev_cursor = await svc.list(...)
    return build_cursor_page(
        [XResponse.model_validate(x) for x in items], next_cursor, prev_cursor, params.limit,
    )
```
