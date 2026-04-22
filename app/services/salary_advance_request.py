import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import OffsetParams, count_from, paginate_offset
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
        params: OffsetParams,
    ) -> tuple[list[SalaryAdvanceRequest], int]:
        stmt = (
            select(SalaryAdvanceRequest)
            .where(
                SalaryAdvanceRequest.tenant_id == tenant_id,
                SalaryAdvanceRequest.requester_id == user_id,
            )
            .order_by(SalaryAdvanceRequest.created_at.desc(), SalaryAdvanceRequest.id.desc())
        )
        return await paginate_offset(
            self._db, stmt=stmt, count_stmt=count_from(stmt), params=params
        )

    async def list_for_admin(
        self,
        *,
        tenant_id: uuid.UUID,
        params: OffsetParams,
        status: SalaryAdvanceStatus | None = None,
    ) -> tuple[list[SalaryAdvanceRequest], int]:
        stmt = select(SalaryAdvanceRequest).where(SalaryAdvanceRequest.tenant_id == tenant_id)
        if status is not None:
            stmt = stmt.where(SalaryAdvanceRequest.status == status)
        stmt = stmt.order_by(
            SalaryAdvanceRequest.created_at.desc(), SalaryAdvanceRequest.id.desc()
        )
        return await paginate_offset(
            self._db, stmt=stmt, count_stmt=count_from(stmt), params=params
        )

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
