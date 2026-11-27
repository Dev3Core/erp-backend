"""Endpoints for the Chrome extension. Authenticated via API key (X-API-Key
header or Authorization: Bearer). Kept separate from the JWT-based endpoints
so the extension has a small, stable surface."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity import CurrentApiKeyUser
from app.modules.studio import MacroResponse, MacroService, Platform
from app.shared.database import get_db
from app.shared.pagination import OffsetPage, OffsetParams, build_offset_page, offset_params

router = APIRouter(prefix="/ext", tags=["extension"])


@router.get("/me", response_model=dict)
async def ext_me(user: CurrentApiKeyUser):
    """Minimal identity for the extension. No role exposure beyond what it needs."""
    return {
        "user_id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "tenant_id": str(user.tenant_id),
    }


@router.get("/macros", response_model=OffsetPage[MacroResponse])
async def ext_macros(
    user: CurrentApiKeyUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    params: Annotated[OffsetParams, Depends(offset_params)],
    platform: Annotated[Platform | None, Query()] = None,
):
    svc = MacroService(db)
    items, total = await svc.list_for_user(
        tenant_id=user.tenant_id,
        user_id=user.id,
        params=params,
        platform=platform,
        active_only=True,
    )
    return build_offset_page([MacroResponse.model_validate(x) for x in items], total, params)
