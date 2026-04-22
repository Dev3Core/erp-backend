import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser
from app.core.tenant import CurrentTenantId
from app.database import get_db
from app.schemas.api_key import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyListResponse,
    ApiKeyResponse,
)
from app.services.api_key import ApiKeyService
from app.services.errors import ServiceError

router = APIRouter(prefix="/auth/api-keys", tags=["auth"])


def _get_service(db: Annotated[AsyncSession, Depends(get_db)]) -> ApiKeyService:
    return ApiKeyService(db)


ServiceDep = Annotated[ApiKeyService, Depends(_get_service)]


@router.post(
    "",
    response_model=ApiKeyCreated,
    status_code=status.HTTP_201_CREATED,
)
async def issue_api_key(
    body: ApiKeyCreate,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    svc: ServiceDep,
):
    """Issue a short-lived API key for the caller (typically a MODEL using the
    Chrome extension). Returns the plaintext key ONCE. Store it; it cannot be
    recovered later."""
    entry, plaintext = await svc.issue(
        tenant_id=tenant_id,
        user=user,
        name=body.name,
        ttl_hours=body.ttl_hours,
    )
    return ApiKeyCreated(
        id=entry.id,
        name=entry.name,
        plaintext_key=plaintext,
        prefix=entry.prefix,
        expires_at=entry.expires_at,
    )


@router.get("", response_model=ApiKeyListResponse)
async def list_my_keys(
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    svc: ServiceDep,
    include_revoked: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items, total = await svc.list_for_user(
        tenant_id=tenant_id,
        user_id=user.id,
        include_revoked=include_revoked,
        limit=limit,
        offset=offset,
    )
    return ApiKeyListResponse(items=[ApiKeyResponse.model_validate(x) for x in items], total=total)


@router.delete(
    "/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_api_key(
    key_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    svc: ServiceDep,
):
    try:
        await svc.revoke(tenant_id=tenant_id, key_id=key_id, acting_user_id=user.id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None
    return None
