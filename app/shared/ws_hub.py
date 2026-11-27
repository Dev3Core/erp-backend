"""In-process fan-out hub for WebSocket chat. Keyed by (tenant_id, shift_id).

This is process-local; for multi-worker prod, replace with a Redis pub/sub
fan-out. For the MVP (single uvicorn worker per container) it's enough.
"""

import asyncio
import contextlib
import uuid
from collections import defaultdict

from starlette.websockets import WebSocket


class WebSocketHub:
    def __init__(self) -> None:
        self._channels: dict[tuple[uuid.UUID, uuid.UUID], set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def join(self, *, tenant_id: uuid.UUID, shift_id: uuid.UUID, ws: WebSocket) -> None:
        async with self._lock:
            self._channels[(tenant_id, shift_id)].add(ws)

    async def leave(self, *, tenant_id: uuid.UUID, shift_id: uuid.UUID, ws: WebSocket) -> None:
        async with self._lock:
            subs = self._channels.get((tenant_id, shift_id))
            if subs is not None:
                subs.discard(ws)
                if not subs:
                    self._channels.pop((tenant_id, shift_id), None)

    async def broadcast(self, *, tenant_id: uuid.UUID, shift_id: uuid.UUID, payload: dict) -> None:
        async with self._lock:
            subs = list(self._channels.get((tenant_id, shift_id), set()))
        # Client may have gone away mid-broadcast; leave() will clean it on disconnect.
        for ws in subs:
            with contextlib.suppress(Exception):
                await ws.send_json(payload)


hub = WebSocketHub()
