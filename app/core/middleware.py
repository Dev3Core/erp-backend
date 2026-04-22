from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_STRICT_CSP = "default-src 'self'; frame-ancestors 'none'"

# Swagger UI + ReDoc load assets from jsdelivr and favicon from fastapi.tiangolo.com.
# We relax CSP only on those routes so API responses keep the strict policy.
_DOCS_CSP = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
    "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "font-src 'self' https://cdn.jsdelivr.net data:; "
    "worker-src 'self' blob:; "
    "frame-ancestors 'none'"
)

_DOCS_PATHS = ("/docs", "/redoc")

_BASE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}


def _is_docs_path(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in _DOCS_PATHS)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        for k, v in _BASE_HEADERS.items():
            response.headers.setdefault(k, v)
        response.headers.setdefault(
            "Content-Security-Policy",
            _DOCS_CSP if _is_docs_path(request.url.path) else _STRICT_CSP,
        )
        for leak in ("Server", "X-Powered-By"):
            if leak in response.headers:
                del response.headers[leak]
        return response
