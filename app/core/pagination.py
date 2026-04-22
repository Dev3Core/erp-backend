"""Centralized pagination primitives.

Two modes:

- **Offset** (`OffsetPage`): standard `limit`/`offset` with a hard cap on
  `offset + limit` to prevent DoS. Fine for bounded CRUD resources.
- **Cursor** (`CursorPage`): opaque base64-encoded `(created_at, id)` cursor
  for time-series / append-heavy tables. O(1) per page regardless of depth.
  No `count(*)` — skips the seqscan on huge tables.

Every list endpoint should pick one and stick with it. Mutually exclusive.
"""

from __future__ import annotations

import base64
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any, Generic, TypeVar

from fastapi import HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Select, and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")

# --- Offset pagination -----------------------------------------------------

OFFSET_MAX = 5000
OFFSET_LIMIT_MAX = 200
OFFSET_LIMIT_DEFAULT = 50


@dataclass(frozen=True, slots=True)
class OffsetParams:
    limit: int
    offset: int


def offset_params(
    limit: Annotated[int, Query(ge=1, le=OFFSET_LIMIT_MAX)] = OFFSET_LIMIT_DEFAULT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> OffsetParams:
    if offset + limit > OFFSET_MAX:
        raise HTTPException(
            status_code=422,
            detail=(
                f"offset+limit must be <= {OFFSET_MAX}; "
                "use cursor-based pagination for deeper pages."
            ),
        )
    return OffsetParams(limit=limit, offset=offset)


OffsetPaginationDep = Annotated[OffsetParams, Query()]  # for typing in routes


class OffsetPage(BaseModel, Generic[T]):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    items: list[T]
    total: int
    limit: int
    offset: int
    has_next: bool
    has_prev: bool


async def paginate_offset(
    db: AsyncSession,
    *,
    stmt: Select,
    count_stmt: Select,
    params: OffsetParams,
) -> tuple[list[Any], int]:
    """Execute the select + count with the given offset params. Caller wraps
    the result into the concrete `OffsetPage[T]` subclass."""
    paged = stmt.limit(params.limit).offset(params.offset)
    items = list((await db.execute(paged)).scalars().all())
    total = (await db.execute(count_stmt)).scalar_one()
    return items, total


def build_offset_page(items: list[T], total: int, params: OffsetParams) -> OffsetPage[T]:
    return OffsetPage[T](
        items=items,
        total=total,
        limit=params.limit,
        offset=params.offset,
        has_next=params.offset + len(items) < total,
        has_prev=params.offset > 0,
    )


# --- Cursor pagination -----------------------------------------------------

CURSOR_LIMIT_MAX = 100
CURSOR_LIMIT_DEFAULT = 50


class _CursorDirection:
    NEXT = "next"
    PREV = "prev"


def _encode_cursor(*, created_at: datetime, id_: uuid.UUID, direction: str) -> str:
    payload = json.dumps(
        {
            "t": created_at.astimezone(UTC).isoformat(),
            "i": str(id_),
            "d": direction,
        },
        separators=(",", ":"),
    )
    return base64.urlsafe_b64encode(payload.encode("utf-8")).rstrip(b"=").decode("ascii")


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID, str]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        data = json.loads(raw)
        created_at = datetime.fromisoformat(data["t"])
        id_ = uuid.UUID(data["i"])
        direction = data["d"]
        if direction not in (_CursorDirection.NEXT, _CursorDirection.PREV):
            raise ValueError("bad direction")
    except (ValueError, KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=422, detail="Invalid cursor") from exc
    return created_at, id_, direction


@dataclass(frozen=True, slots=True)
class CursorParams:
    cursor: str | None
    limit: int


def cursor_params(
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=CURSOR_LIMIT_MAX)] = CURSOR_LIMIT_DEFAULT,
) -> CursorParams:
    return CursorParams(cursor=cursor, limit=limit)


class CursorPage(BaseModel, Generic[T]):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    items: list[T]
    next_cursor: str | None
    prev_cursor: str | None
    limit: int


async def paginate_cursor(
    db: AsyncSession,
    *,
    stmt: Select,
    params: CursorParams,
    created_col,
    id_col,
) -> tuple[list[Any], str | None, str | None]:
    """Cursor pagination for time-series. ALWAYS orders by
    `(created_col DESC, id_col DESC)` for stable sort with duplicate timestamps.

    The cursor encodes the (created_at, id) of the last row seen plus the
    direction the client was going. We fetch `limit + 1` rows to detect
    whether more exist.

    Returns: (items[:limit], next_cursor, prev_cursor).
    """
    base = stmt.order_by(desc(created_col), desc(id_col))

    if params.cursor is None:
        paged = base.limit(params.limit + 1)
        rows = list((await db.execute(paged)).scalars().all())
        has_more = len(rows) > params.limit
        items = rows[: params.limit]
        next_cursor = (
            _encode_cursor(
                created_at=getattr(items[-1], created_col.key),
                id_=getattr(items[-1], id_col.key),
                direction=_CursorDirection.NEXT,
            )
            if has_more and items
            else None
        )
        return items, next_cursor, None

    cursor_ts, cursor_id, direction = _decode_cursor(params.cursor)

    # Tuple comparison written explicitly as (col1 < ts) OR (col1 == ts AND col2 < id)
    # because SQLite doesn't support the ROW(...) < (..., ...) syntax that `tuple_(...)` emits.
    def _before(ts, ident):
        return or_(created_col < ts, and_(created_col == ts, id_col < ident))

    def _after(ts, ident):
        return or_(created_col > ts, and_(created_col == ts, id_col > ident))

    if direction == _CursorDirection.NEXT:
        paged = base.where(_before(cursor_ts, cursor_id)).limit(params.limit + 1)
        rows = list((await db.execute(paged)).scalars().all())
        has_more = len(rows) > params.limit
        items = rows[: params.limit]
        next_cursor = (
            _encode_cursor(
                created_at=getattr(items[-1], created_col.key),
                id_=getattr(items[-1], id_col.key),
                direction=_CursorDirection.NEXT,
            )
            if has_more and items
            else None
        )
        prev_cursor = (
            _encode_cursor(
                created_at=getattr(items[0], created_col.key),
                id_=getattr(items[0], id_col.key),
                direction=_CursorDirection.PREV,
            )
            if items
            else None
        )
        return items, next_cursor, prev_cursor

    # PREV direction: walk forward through time, then reverse the page.
    prev_stmt = (
        stmt.order_by(created_col.asc(), id_col.asc())
        .where(_after(cursor_ts, cursor_id))
        .limit(params.limit + 1)
    )
    rows = list((await db.execute(prev_stmt)).scalars().all())
    has_more = len(rows) > params.limit
    items = list(reversed(rows[: params.limit]))
    next_cursor = (
        _encode_cursor(
            created_at=getattr(items[-1], created_col.key),
            id_=getattr(items[-1], id_col.key),
            direction=_CursorDirection.NEXT,
        )
        if items
        else None
    )
    prev_cursor = (
        _encode_cursor(
            created_at=getattr(items[0], created_col.key),
            id_=getattr(items[0], id_col.key),
            direction=_CursorDirection.PREV,
        )
        if has_more and items
        else None
    )
    return items, next_cursor, prev_cursor


def build_cursor_page(
    items: list[T], next_cursor: str | None, prev_cursor: str | None, limit: int
) -> CursorPage[T]:
    return CursorPage[T](
        items=items, next_cursor=next_cursor, prev_cursor=prev_cursor, limit=limit
    )


# --- Convenience: stable ORDER BY helper for offset pagination ------------


def stable_order(stmt: Select, *cols) -> Select:
    """Append `id` (or the provided cols) as tiebreakers so offset pagination
    doesn't yield duplicates/gaps when the primary sort column has ties."""
    return stmt.order_by(*cols)


# --- For external re-use ---------------------------------------------------

__all__ = [
    "CURSOR_LIMIT_DEFAULT",
    "CURSOR_LIMIT_MAX",
    "OFFSET_LIMIT_DEFAULT",
    "OFFSET_LIMIT_MAX",
    "OFFSET_MAX",
    "CursorPage",
    "CursorParams",
    "OffsetPage",
    "OffsetParams",
    "build_cursor_page",
    "build_offset_page",
    "cursor_params",
    "offset_params",
    "paginate_cursor",
    "paginate_offset",
    "stable_order",
]


# --- Total count helper for offset pages ---------------------------------


def count_from(stmt: Select) -> Select:
    """Given a select, return the corresponding `SELECT COUNT(*)`."""
    return select(func.count()).select_from(stmt.order_by(None).subquery())
