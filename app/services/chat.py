import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_message import ChatMessage
from app.models.shift import Shift
from app.models.user import Role, User
from app.services.errors import ForbiddenError, NotFoundError


class ChatService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def post(
        self,
        *,
        tenant_id: uuid.UUID,
        shift_id: uuid.UUID,
        sender: User,
        body: str,
    ) -> ChatMessage:
        await self._ensure_participant(tenant_id=tenant_id, shift_id=shift_id, user=sender)
        msg = ChatMessage(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            shift_id=shift_id,
            sender_id=sender.id,
            body=body,
        )
        self._db.add(msg)
        await self._db.flush()
        return msg

    async def list_for_shift(
        self,
        *,
        tenant_id: uuid.UUID,
        shift_id: uuid.UUID,
        actor: User,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ChatMessage], int]:
        await self._ensure_participant(tenant_id=tenant_id, shift_id=shift_id, user=actor)
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.tenant_id == tenant_id, ChatMessage.shift_id == shift_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        count_stmt = (
            select(func.count())
            .select_from(ChatMessage)
            .where(ChatMessage.tenant_id == tenant_id, ChatMessage.shift_id == shift_id)
        )
        items = list((await self._db.execute(stmt)).scalars().all())
        total = (await self._db.execute(count_stmt)).scalar_one()
        return items, total

    async def _ensure_participant(
        self, *, tenant_id: uuid.UUID, shift_id: uuid.UUID, user: User
    ) -> Shift:
        """A shift's chat is open to: the model, the assigned monitor, or any OWNER/ADMIN."""
        stmt = select(Shift).where(Shift.id == shift_id, Shift.tenant_id == tenant_id)
        shift = (await self._db.execute(stmt)).scalar_one_or_none()
        if shift is None:
            raise NotFoundError("Shift not found")
        allowed = user.role in (Role.OWNER, Role.ADMIN)
        allowed = allowed or shift.model_id == user.id
        allowed = allowed or shift.monitor_id == user.id
        if not allowed:
            raise ForbiddenError("Not a participant of this shift chat")
        return shift
