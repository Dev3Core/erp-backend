from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser
from app.core.pagination import CursorPage, CursorParams, build_cursor_page, cursor_params
from app.core.tenant import CurrentTenantId
from app.database import get_db
from app.schemas.notification import NotificationMarkRead, NotificationResponse
from app.services.notification import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _get_service(db: Annotated[AsyncSession, Depends(get_db)]) -> NotificationService:
    return NotificationService(db)


ServiceDep = Annotated[NotificationService, Depends(_get_service)]


@router.get("", response_model=CursorPage[NotificationResponse])
async def list_notifications(
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    svc: ServiceDep,
    params: Annotated[CursorParams, Depends(cursor_params)],
    unread_only: Annotated[bool, Query()] = False,
):
    items, next_cursor, prev_cursor = await svc.list_for_user(
        tenant_id=tenant_id,
        user_id=user.id,
        params=params,
        unread_only=unread_only,
    )
    return build_cursor_page(
        [NotificationResponse.model_validate(x) for x in items],
        next_cursor,
        prev_cursor,
        params.limit,
    )


@router.get("/unread-count", response_model=dict)
async def get_unread_count(
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    svc: ServiceDep,
):
    return {"unread_count": await svc.unread_count(tenant_id=tenant_id, user_id=user.id)}


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
