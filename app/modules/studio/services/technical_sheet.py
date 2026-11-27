import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity import Role, user_has_role_in_tenant
from app.modules.studio.models.technical_sheet import TechnicalSheet
from app.shared.errors import NotFoundError, ValidationError
from app.shared.pagination import OffsetParams, count_from, paginate_offset


class TechnicalSheetService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(
        self,
        *,
        tenant_id: uuid.UUID,
        model_id: uuid.UUID,
        bio: str | None,
        languages: str | None,
        categories: str | None,
        notes: str | None,
    ) -> TechnicalSheet:
        await self._ensure_model_in_tenant(tenant_id=tenant_id, model_id=model_id)

        sheet = TechnicalSheet(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            model_id=model_id,
            bio=bio,
            languages=languages,
            categories=categories,
            notes=notes,
        )
        self._db.add(sheet)
        await self._db.flush()
        return sheet

    async def list(
        self,
        *,
        tenant_id: uuid.UUID,
        params: OffsetParams,
        model_id: uuid.UUID | None = None,
    ) -> tuple[list[TechnicalSheet], int]:
        stmt = select(TechnicalSheet).where(TechnicalSheet.tenant_id == tenant_id)
        if model_id is not None:
            stmt = stmt.where(TechnicalSheet.model_id == model_id)
        stmt = stmt.order_by(TechnicalSheet.created_at.desc(), TechnicalSheet.id.desc())
        return await paginate_offset(
            self._db, stmt=stmt, count_stmt=count_from(stmt), params=params
        )

    async def get(self, *, tenant_id: uuid.UUID, sheet_id: uuid.UUID) -> TechnicalSheet:
        return await self._get_in_tenant(tenant_id=tenant_id, sheet_id=sheet_id)

    async def update(
        self,
        *,
        tenant_id: uuid.UUID,
        sheet_id: uuid.UUID,
        bio: str | None,
        languages: str | None,
        categories: str | None,
        notes: str | None,
    ) -> TechnicalSheet:
        sheet = await self._get_in_tenant(tenant_id=tenant_id, sheet_id=sheet_id)

        if bio is not None:
            sheet.bio = bio
        if languages is not None:
            sheet.languages = languages
        if categories is not None:
            sheet.categories = categories
        if notes is not None:
            sheet.notes = notes

        await self._db.flush()
        await self._db.refresh(sheet, ["updated_at"])
        return sheet

    async def delete(self, *, tenant_id: uuid.UUID, sheet_id: uuid.UUID) -> None:
        sheet = await self._get_in_tenant(tenant_id=tenant_id, sheet_id=sheet_id)
        await self._db.delete(sheet)
        await self._db.flush()

    async def _get_in_tenant(self, *, tenant_id: uuid.UUID, sheet_id: uuid.UUID) -> TechnicalSheet:
        stmt = select(TechnicalSheet).where(
            TechnicalSheet.id == sheet_id,
            TechnicalSheet.tenant_id == tenant_id,
        )
        sheet = (await self._db.execute(stmt)).scalar_one_or_none()
        if sheet is None:
            raise NotFoundError("Technical sheet not found")
        return sheet

    async def _ensure_model_in_tenant(self, *, tenant_id: uuid.UUID, model_id: uuid.UUID) -> None:
        if not await user_has_role_in_tenant(
            self._db, tenant_id=tenant_id, user_id=model_id, role=Role.MODEL
        ):
            raise ValidationError("Target user is not a MODEL of this tenant")
