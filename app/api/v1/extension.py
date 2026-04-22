"""Endpoints for the Chrome extension. Authenticated via API key (X-API-Key
header or Authorization: Bearer). Kept separate from the JWT-based endpoints
so the extension has a small, stable surface."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api_key_auth import CurrentApiKeyUser
from app.database import get_db
from app.models.room import Platform
from app.schemas.macro import MacroListResponse, MacroResponse
from app.services.macro import MacroService

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


@router.get("/macros", response_model=MacroListResponse)
async def ext_macros(
    user: CurrentApiKeyUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    platform: Annotated[Platform | None, Query()] = None,
):
    svc = MacroService(db)
    items, total = await svc.list_for_user(
        tenant_id=user.tenant_id,
        user_id=user.id,
        platform=platform,
        active_only=True,
    )
    return MacroListResponse(items=[MacroResponse.model_validate(x) for x in items], total=total)
