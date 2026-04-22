"""Tests for the centralized pagination primitives (offset cap, cursor roundtrip, stable sort)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.core.pagination import (
    OFFSET_LIMIT_MAX,
    OFFSET_MAX,
    _decode_cursor,
    _encode_cursor,
)


class TestOffsetParams:
    async def test_offset_cap_blocks_deep_pages(self, owner_client_a: AsyncClient):
        resp = await owner_client_a.get(f"/api/v1/users?limit=200&offset={OFFSET_MAX}")
        assert resp.status_code == 422
        assert "cursor" in resp.text.lower()

    async def test_offset_limit_upper_bound(self, owner_client_a: AsyncClient):
        resp = await owner_client_a.get(f"/api/v1/users?limit={OFFSET_LIMIT_MAX + 1}")
        assert resp.status_code == 422

    async def test_offset_page_shape(self, owner_client_a: AsyncClient):
        resp = await owner_client_a.get("/api/v1/users")
        assert resp.status_code == 200
        data = resp.json()
        assert set(data.keys()) == {"items", "total", "limit", "offset", "has_next", "has_prev"}
        assert data["offset"] == 0
        assert data["has_prev"] is False

    async def test_offset_has_next_flag(self, owner_client_a: AsyncClient):
        # Create enough users to exceed one page
        for i in range(3):
            await owner_client_a.post(
                "/api/v1/users",
                json={
                    "email": f"paginated{i}@a.com",
                    "password": "StrongPass123",
                    "full_name": f"Page User {i}",
                    "role": "MONITOR",
                },
            )
        resp = await owner_client_a.get("/api/v1/users?limit=2&offset=0")
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["has_next"] is True
        assert data["has_prev"] is False

        resp2 = await owner_client_a.get("/api/v1/users?limit=2&offset=2")
        assert resp2.json()["has_prev"] is True


class TestCursorRoundtrip:
    def test_encode_decode_roundtrip(self):
        ts = datetime(2026, 4, 22, 15, 30, 0, tzinfo=UTC)
        ident = uuid.uuid4()
        cursor = _encode_cursor(created_at=ts, id_=ident, direction="next")
        got_ts, got_id, got_dir = _decode_cursor(cursor)
        assert got_ts == ts
        assert got_id == ident
        assert got_dir == "next"

    def test_decode_bad_cursor_rejected(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            _decode_cursor("not-valid-base64!!!")
        assert exc.value.status_code == 422


class TestCursorPagination:
    async def test_cursor_page_shape(self, owner_client_a: AsyncClient):
        resp = await owner_client_a.get("/api/v1/shifts")
        assert resp.status_code == 200
        data = resp.json()
        assert set(data.keys()) == {"items", "next_cursor", "prev_cursor", "limit"}

    async def test_cursor_walk_forward(self, owner_client_a: AsyncClient):
        """Create 5 shifts, paginate 2-by-2 forward via cursors."""
        # Seed a model + room + shifts
        mid = (
            await owner_client_a.post(
                "/api/v1/users",
                json={
                    "email": "walk_model@a.com",
                    "password": "StrongPass123",
                    "full_name": "Walk",
                    "role": "MODEL",
                },
            )
        ).json()["id"]
        rid = (
            await owner_client_a.post(
                "/api/v1/rooms",
                json={
                    "name": "Walk Room",
                    "platform": "CHATURBATE",
                    "url": "https://chaturbate.com/walk/",
                },
            )
        ).json()["id"]
        base = datetime.now(UTC).replace(microsecond=0)
        ids = []
        for i in range(5):
            r = await owner_client_a.post(
                "/api/v1/shifts",
                json={
                    "model_id": mid,
                    "room_id": rid,
                    "start_time": (base + timedelta(hours=i)).isoformat(),
                    "end_time": (base + timedelta(hours=i + 1)).isoformat(),
                },
            )
            ids.append(r.json()["id"])

        # First page
        p1 = await owner_client_a.get("/api/v1/shifts?limit=2")
        d1 = p1.json()
        assert len(d1["items"]) == 2
        assert d1["next_cursor"] is not None

        # Second page
        p2 = await owner_client_a.get(f"/api/v1/shifts?limit=2&cursor={d1['next_cursor']}")
        d2 = p2.json()
        assert len(d2["items"]) == 2
        assert d2["next_cursor"] is not None

        # Third page
        p3 = await owner_client_a.get(f"/api/v1/shifts?limit=2&cursor={d2['next_cursor']}")
        d3 = p3.json()
        assert len(d3["items"]) == 1
        assert d3["next_cursor"] is None

        # Cursor-returned items should be a contiguous non-overlapping sequence.
        seen = [x["id"] for x in d1["items"] + d2["items"] + d3["items"]]
        assert len(seen) == len(set(seen))

    async def test_bad_cursor_rejected(self, owner_client_a: AsyncClient):
        resp = await owner_client_a.get("/api/v1/shifts?cursor=garbage")
        assert resp.status_code == 422
