import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.html_sanitizer import sanitize_bio_html
from app.core.pagination import OffsetParams, count_from, paginate_offset
from app.models.bio_template import BioTemplate
from app.services.errors import NotFoundError


class BioTemplateService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(
        self,
        *,
        tenant_id: uuid.UUID,
        created_by: uuid.UUID,
        name: str,
        html_content: str,
    ) -> BioTemplate:
        entry = BioTemplate(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            created_by=created_by,
            name=name,
            html_content=sanitize_bio_html(html_content),
        )
        self._db.add(entry)
        await self._db.flush()
        return entry

    async def list(
        self,
        *,
        tenant_id: uuid.UUID,
        params: OffsetParams,
        active_only: bool = False,
    ) -> tuple[list[BioTemplate], int]:
        stmt = select(BioTemplate).where(BioTemplate.tenant_id == tenant_id)
        if active_only:
            stmt = stmt.where(BioTemplate.is_active.is_(True))
        stmt = stmt.order_by(BioTemplate.created_at.desc(), BioTemplate.id.desc())
        return await paginate_offset(
            self._db, stmt=stmt, count_stmt=count_from(stmt), params=params
        )

    async def get(self, *, tenant_id: uuid.UUID, template_id: uuid.UUID) -> BioTemplate:
        return await self._get_in_tenant(tenant_id=tenant_id, template_id=template_id)

    async def update(
        self,
        *,
        tenant_id: uuid.UUID,
        template_id: uuid.UUID,
        name: str | None,
        html_content: str | None,
        is_active: bool | None,
    ) -> BioTemplate:
        entry = await self._get_in_tenant(tenant_id=tenant_id, template_id=template_id)
        if name is not None:
            entry.name = name
        if html_content is not None:
            entry.html_content = sanitize_bio_html(html_content)
        if is_active is not None:
            entry.is_active = is_active
        await self._db.flush()
        return entry

    async def delete(self, *, tenant_id: uuid.UUID, template_id: uuid.UUID) -> None:
        entry = await self._get_in_tenant(tenant_id=tenant_id, template_id=template_id)
        await self._db.delete(entry)
        await self._db.flush()

    async def _get_in_tenant(self, *, tenant_id: uuid.UUID, template_id: uuid.UUID) -> BioTemplate:
        stmt = select(BioTemplate).where(
            BioTemplate.id == template_id, BioTemplate.tenant_id == tenant_id
        )
        entry = (await self._db.execute(stmt)).scalar_one_or_none()
        if entry is None:
            raise NotFoundError("Bio template not found")
        return entry
