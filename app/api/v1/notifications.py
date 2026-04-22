from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser
from app.core.tenant import CurrentTenantId
from app.database import get_db
from app.schemas.notification import (
    NotificationListResponse,
    NotificationMarkRead,
    NotificationResponse,
)
from app.services.notification import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _get_service(db: Annotated[AsyncSession, Depends(get_db)]) -> NotificationService:
    return NotificationService(db)


ServiceDep = Annotated[NotificationService, Depends(_get_service)]


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    svc: ServiceDep,
    unread_only: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items, total, unread = await svc.list_for_user(
        tenant_id=tenant_id,
        user_id=user.id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )
    return NotificationListResponse(
        items=[NotificationResponse.model_validate(x) for x in items],
        total=total,
        unread_count=unread,
    )


@router.post("/mark-read", response_model=dict)
async def mark_read(
    body: NotificationMarkRead,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    svc: ServiceDep,
):
    n = await svc.mark_read(tenant_id=tenant_id, user_id=user.id, ids=body.ids)
    return {"marked": n}


@router.post("/mark-all-read", response_model=dict)
async def mark_all_read(
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    svc: ServiceDep,
):
    n = await svc.mark_all_read(tenant_id=tenant_id, user_id=user.id)
    return {"marked": n}
