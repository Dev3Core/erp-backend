from httpx import AsyncClient

REGISTER_PAYLOAD = {
    "studio_name": "Rate Studio",
    "full_name": "RL Tester",
    "email": "rl@example.com",
    "password": "StrongPass123",
}


def _unique_register(i: int) -> dict:
    return {
        **REGISTER_PAYLOAD,
        "studio_name": f"Rate Studio {i}",
        "email": f"rl{i}@example.com",
    }


async def test_register_rate_limit_blocks_after_threshold(client: AsyncClient) -> None:
    # limit = 3/min/IP — first 3 succeed, 4th must be 429.
    for i in range(3):
        resp = await client.post("/api/v1/auth/register", json=_unique_register(i))
        assert resp.status_code == 201, f"attempt {i} got {resp.status_code}"

    resp = await client.post("/api/v1/auth/register", json=_unique_register(99))
    assert resp.status_code == 429
    assert "retry-after" in {k.lower() for k in resp.headers}
    assert int(resp.headers["retry-after"]) >= 1


async def test_login_rate_limit_blocks_after_threshold(client: AsyncClient) -> None:
    # limit = 5/min/IP. All 5 will 401 (no user), 6th must be 429.
    for _ in range(5):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "WrongPass123"},
        )
        assert resp.status_code == 401

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "WrongPass123"},
    )
    assert resp.status_code == 429
