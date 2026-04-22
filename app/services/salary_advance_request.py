import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.salary_advance_request import SalaryAdvanceRequest, SalaryAdvanceStatus
from app.models.user import Role, User
from app.services.errors import ForbiddenError, NotFoundError, ValidationError

_ALLOWED_TRANSITIONS: dict[SalaryAdvanceStatus, set[SalaryAdvanceStatus]] = {
    SalaryAdvanceStatus.PENDING: {
        SalaryAdvanceStatus.APPROVED,
        SalaryAdvanceStatus.REJECTED,
    },
    SalaryAdvanceStatus.APPROVED: {SalaryAdvanceStatus.PAID},
    SalaryAdvanceStatus.REJECTED: set(),
    SalaryAdvanceStatus.PAID: set(),
}


class SalaryAdvanceService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def request(
        self,
        *,
        tenant_id: uuid.UUID,
        requester: User,
        amount_cop: Decimal,
        reason: str | None,
    ) -> SalaryAdvanceRequest:
        entry = SalaryAdvanceRequest(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            requester_id=requester.id,
            amount_cop=amount_cop,
            reason=reason,
        )
        self._db.add(entry)
        await self._db.flush()
        return entry

    async def list_mine(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SalaryAdvanceRequest], int]:
        stmt = select(SalaryAdvanceRequest).where(
            SalaryAdvanceRequest.tenant_id == tenant_id,
            SalaryAdvanceRequest.requester_id == user_id,
        )
        count_stmt = (
            select(func.count())
            .select_from(SalaryAdvanceRequest)
            .where(
                SalaryAdvanceRequest.tenant_id == tenant_id,
                SalaryAdvanceRequest.requester_id == user_id,
            )
        )
        stmt = stmt.order_by(SalaryAdvanceRequest.created_at.desc()).limit(limit).offset(offset)
        items = list((await self._db.execute(stmt)).scalars().all())
        total = (await self._db.execute(count_stmt)).scalar_one()
        return items, total

    async def list_for_admin(
        self,
        *,
        tenant_id: uuid.UUID,
        status: SalaryAdvanceStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SalaryAdvanceRequest], int]:
        stmt = select(SalaryAdvanceRequest).where(SalaryAdvanceRequest.tenant_id == tenant_id)
        count_stmt = (
            select(func.count())
            .select_from(SalaryAdvanceRequest)
            .where(SalaryAdvanceRequest.tenant_id == tenant_id)
        )
        if status is not None:
            stmt = stmt.where(SalaryAdvanceRequest.status == status)
            count_stmt = count_stmt.where(SalaryAdvanceRequest.status == status)
        stmt = stmt.order_by(SalaryAdvanceRequest.created_at.desc()).limit(limit).offset(offset)
        items = list((await self._db.execute(stmt)).scalars().all())
        total = (await self._db.execute(count_stmt)).scalar_one()
        return items, total

    async def review(
        self,
        *,
        tenant_id: uuid.UUID,
        request_id: uuid.UUID,
        reviewer: User,
        new_status: SalaryAdvanceStatus,
        review_notes: str | None,
    ) -> SalaryAdvanceRequest:
        if reviewer.role not in (Role.OWNER, Role.ADMIN):
            raise ForbiddenError("Only OWNER or ADMIN can review advance requests")

        entry = await self._get_in_tenant(tenant_id=tenant_id, request_id=request_id)
        if new_status not in _ALLOWED_TRANSITIONS.get(entry.status, set()):
            raise ValidationError(
                f"Invalid status transition {entry.status.value} -> {new_status.value}"
            )
        entry.status = new_status
        entry.reviewer_id = reviewer.id
        entry.reviewed_at = datetime.now(UTC)
        if review_notes is not None:
            entry.review_notes = review_notes
        await self._db.flush()
        return entry

    async def get(
        self, *, tenant_id: uuid.UUID, request_id: uuid.UUID, actor: User
    ) -> SalaryAdvanceRequest:
        entry = await self._get_in_tenant(tenant_id=tenant_id, request_id=request_id)
        if actor.role not in (Role.OWNER, Role.ADMIN) and entry.requester_id != actor.id:
            raise NotFoundError("Salary advance request not found")
        return entry

    async def _get_in_tenant(
        self, *, tenant_id: uuid.UUID, request_id: uuid.UUID
    ) -> SalaryAdvanceRequest:
        stmt = select(SalaryAdvanceRequest).where(
            SalaryAdvanceRequest.id == request_id,
            SalaryAdvanceRequest.tenant_id == tenant_id,
        )
        entry = (await self._db.execute(stmt)).scalar_one_or_none()
        if entry is None:
            raise NotFoundError("Salary advance request not found")
        return entry
