from httpx import AsyncClient

EXPECTED = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "strict-origin-when-cross-origin",
    "strict-transport-security": "max-age=63072000; includeSubDomains",
    "content-security-policy": "default-src 'self'; frame-ancestors 'none'",
    "permissions-policy": "geolocation=(), microphone=(), camera=()",
    "cross-origin-opener-policy": "same-origin",
    "cross-origin-resource-policy": "same-origin",
}


async def test_security_headers_present_on_success(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    for header, value in EXPECTED.items():
        assert resp.headers.get(header) == value, f"missing/mismatched {header}"


async def test_security_headers_present_on_error(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
    for header in EXPECTED:
        assert header in resp.headers, f"{header} missing on 404"


async def test_server_header_stripped(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/health")
    assert "server" not in {k.lower() for k in resp.headers}
    assert "x-powered-by" not in {k.lower() for k in resp.headers}
