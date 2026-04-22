import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationKind


class NotificationService:
    """Store-and-retrieve for in-app notifications. Can be emitted from any
    service (typically after a business event: shift start, goal hit, etc.)."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def emit(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        kind: NotificationKind,
        title: str,
        body: str | None = None,
        meta: dict | None = None,
    ) -> Notification:
        entry = Notification(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            kind=kind,
            title=title,
            body=body,
            meta=meta,
        )
        self._db.add(entry)
        await self._db.flush()
        return entry

    async def list_for_user(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Notification], int, int]:
        stmt = select(Notification).where(
            Notification.tenant_id == tenant_id,
            Notification.user_id == user_id,
        )
        count_stmt = (
            select(func.count())
            .select_from(Notification)
            .where(Notification.tenant_id == tenant_id, Notification.user_id == user_id)
        )
        unread_stmt = (
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.tenant_id == tenant_id,
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
        )
        if unread_only:
            stmt = stmt.where(Notification.read_at.is_(None))
            count_stmt = count_stmt.where(Notification.read_at.is_(None))

        stmt = stmt.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
        items = list((await self._db.execute(stmt)).scalars().all())
        total = (await self._db.execute(count_stmt)).scalar_one()
        unread = (await self._db.execute(unread_stmt)).scalar_one()
        return items, total, unread

    async def mark_read(
        self, *, tenant_id: uuid.UUID, user_id: uuid.UUID, ids: list[uuid.UUID]
    ) -> int:
        now = datetime.now(UTC)
        result = await self._db.execute(
            update(Notification)
            .where(
                Notification.tenant_id == tenant_id,
                Notification.user_id == user_id,
                Notification.id.in_(ids),
                Notification.read_at.is_(None),
            )
            .values(read_at=now)
        )
        await self._db.flush()
        return result.rowcount or 0

    async def mark_all_read(self, *, tenant_id: uuid.UUID, user_id: uuid.UUID) -> int:
        now = datetime.now(UTC)
        result = await self._db.execute(
            update(Notification)
            .where(
                Notification.tenant_id == tenant_id,
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
            .values(read_at=now)
        )
        await self._db.flush()
        return result.rowcount or 0
