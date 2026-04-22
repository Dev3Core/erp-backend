import uuid
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.split_config import SplitConfig
from app.services.errors import NotFoundError


class SplitConfigService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(
        self,
        *,
        tenant_id: uuid.UUID,
        label: str,
        platform_pct: Decimal,
        studio_pct: Decimal,
        model_pct: Decimal,
        is_default: bool,
    ) -> SplitConfig:
        if is_default:
            await self._clear_default(tenant_id)

        config = SplitConfig(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            label=label,
            platform_pct=platform_pct,
            studio_pct=studio_pct,
            model_pct=model_pct,
            is_default=is_default,
        )
        self._db.add(config)
        await self._db.flush()
        return config

    async def list(
        self,
        *,
        tenant_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SplitConfig], int]:
        stmt = (
            select(SplitConfig)
            .where(SplitConfig.tenant_id == tenant_id)
            .order_by(SplitConfig.is_default.desc(), SplitConfig.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        count_stmt = (
            select(func.count()).select_from(SplitConfig).where(SplitConfig.tenant_id == tenant_id)
        )
        items = list((await self._db.execute(stmt)).scalars().all())
        total = (await self._db.execute(count_stmt)).scalar_one()
        return items, total

    async def get(self, *, tenant_id: uuid.UUID, config_id: uuid.UUID) -> SplitConfig:
        return await self._get_in_tenant(tenant_id=tenant_id, config_id=config_id)

    async def update(
        self,
        *,
        tenant_id: uuid.UUID,
        config_id: uuid.UUID,
        label: str | None,
        platform_pct: Decimal | None,
        studio_pct: Decimal | None,
        model_pct: Decimal | None,
        is_default: bool | None,
    ) -> SplitConfig:
        config = await self._get_in_tenant(tenant_id=tenant_id, config_id=config_id)

        if label is not None:
            config.label = label
        if platform_pct is not None and studio_pct is not None and model_pct is not None:
            config.platform_pct = platform_pct
            config.studio_pct = studio_pct
            config.model_pct = model_pct
        if is_default is True and not config.is_default:
            await self._clear_default(tenant_id)
            config.is_default = True
        elif is_default is False:
            config.is_default = False

        await self._db.flush()
        return config

    async def delete(self, *, tenant_id: uuid.UUID, config_id: uuid.UUID) -> None:
        config = await self._get_in_tenant(tenant_id=tenant_id, config_id=config_id)
        await self._db.delete(config)
        await self._db.flush()

    async def _clear_default(self, tenant_id: uuid.UUID) -> None:
        await self._db.execute(
            update(SplitConfig)
            .where(SplitConfig.tenant_id == tenant_id, SplitConfig.is_default.is_(True))
            .values(is_default=False)
        )

    async def _get_in_tenant(self, *, tenant_id: uuid.UUID, config_id: uuid.UUID) -> SplitConfig:
        stmt = select(SplitConfig).where(
            SplitConfig.id == config_id,
            SplitConfig.tenant_id == tenant_id,
        )
        config = (await self._db.execute(stmt)).scalar_one_or_none()
        if config is None:
            raise NotFoundError("Split config not found")
        return config
