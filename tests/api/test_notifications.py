from httpx import AsyncClient
from sqlalchemy import select

from app.models.notification import Notification, NotificationKind
from tests.conftest import TestingSession


class TestNotifications:
    async def test_list_empty_initially(self, owner_client_a: AsyncClient):
        resp = await owner_client_a.get("/api/v1/notifications")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["unread_count"] == 0

    async def test_mark_read_flow(self, owner_client_a: AsyncClient, tenant_a: dict):
        # Seed notifications directly via the DB.
        import uuid as _u

        async with TestingSession() as session:
            for _ in range(3):
                session.add(
                    Notification(
                        id=_u.uuid4(),
                        tenant_id=_u.UUID(tenant_a["tenant_id"]),
                        user_id=_u.UUID(tenant_a["owner_id"]),
                        kind=NotificationKind.SYSTEM,
                        title="t",
                        body="b",
                    )
                )
            await session.commit()

        listing = await owner_client_a.get("/api/v1/notifications")
        data = listing.json()
        assert data["total"] == 3 and data["unread_count"] == 3
        ids = [n["id"] for n in data["items"][:2]]

        resp = await owner_client_a.post("/api/v1/notifications/mark-read", json={"ids": ids})
        assert resp.status_code == 200 and resp.json()["marked"] == 2

        after = await owner_client_a.get("/api/v1/notifications")
        assert after.json()["unread_count"] == 1

        mark_all = await owner_client_a.post("/api/v1/notifications/mark-all-read")
        assert mark_all.json()["marked"] == 1

    async def test_only_own_notifications_visible(
        self,
        owner_client_a: AsyncClient,
        model_client_a: AsyncClient,
        tenant_a: dict,
    ):
        import uuid as _u

        # Seed one notification for OWNER of tenant A.
        async with TestingSession() as session:
            session.add(
                Notification(
                    id=_u.uuid4(),
                    tenant_id=_u.UUID(tenant_a["tenant_id"]),
                    user_id=_u.UUID(tenant_a["owner_id"]),
                    kind=NotificationKind.SYSTEM,
                    title="private",
                    body="private",
                )
            )
            await session.commit()

        # The model of tenant A should not see the owner's notifications.
        async with TestingSession() as session:
            owner_count = (
                (
                    await session.execute(
                        select(Notification).where(Notification.title == "private")
                    )
                )
                .scalars()
                .all()
            )
            assert len(owner_count) == 1  # only 1 in DB

        model_view = await model_client_a.get("/api/v1/notifications")
        assert model_view.json()["total"] == 0
