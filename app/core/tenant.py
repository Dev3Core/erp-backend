import uuid
from contextvars import ContextVar

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

_current_tenant_id: ContextVar[uuid.UUID | None] = ContextVar(
    "current_tenant_id", default=None
)


def get_current_tenant_id() -> uuid.UUID | None:
    return _current_tenant_id.get()


def set_current_tenant_id(tenant_id: uuid.UUID) -> None:
    _current_tenant_id.set(tenant_id)


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        tenant_header = request.headers.get("X-Tenant-ID")
        if tenant_header:
            try:
                set_current_tenant_id(uuid.UUID(tenant_header))
            except ValueError:
                pass
        return await call_next(request)
