import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser, require_roles
from app.core.tenant import CurrentTenantId
from app.database import get_db
from app.models.user import Role
from app.schemas.user import UserCreate, UserListResponse, UserResponse, UserUpdate
from app.services.errors import ServiceError
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["users"])

AdminOrOwner = require_roles(Role.OWNER, Role.ADMIN)


def _get_service(db: Annotated[AsyncSession, Depends(get_db)]) -> UserService:
    return UserService(db)


UserServiceDep = Annotated[UserService, Depends(_get_service)]


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[AdminOrOwner],
)
async def create_user(
    body: UserCreate,
    tenant_id: CurrentTenantId,
    actor: CurrentUser,
    svc: UserServiceDep,
):
    try:
        user = await svc.create(
            tenant_id=tenant_id,
            actor=actor,
            email=body.email,
            password=body.password,
            full_name=body.full_name,
            role=body.role,
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None
    return user


@router.get("", response_model=UserListResponse, dependencies=[AdminOrOwner])
async def list_users(
    tenant_id: CurrentTenantId,
    svc: UserServiceDep,
    role: Annotated[Role | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items, total = await svc.list(
        tenant_id=tenant_id,
        role=role,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    return UserListResponse(items=[UserResponse.model_validate(u) for u in items], total=total)


@router.get("/{user_id}", response_model=UserResponse, dependencies=[AdminOrOwner])
async def get_user(
    user_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    svc: UserServiceDep,
):
    try:
        return await svc.get(tenant_id=tenant_id, user_id=user_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None


@router.patch("/{user_id}", response_model=UserResponse, dependencies=[AdminOrOwner])
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    tenant_id: CurrentTenantId,
    actor: CurrentUser,
    svc: UserServiceDep,
):
    try:
        return await svc.update(
            tenant_id=tenant_id,
            user_id=user_id,
            actor=actor,
            full_name=body.full_name,
            role=body.role,
            is_active=body.is_active,
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[AdminOrOwner],
)
async def deactivate_user(
    user_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    actor: CurrentUser,
    svc: UserServiceDep,
):
    try:
        await svc.deactivate(tenant_id=tenant_id, user_id=user_id, actor=actor)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None
    return None
