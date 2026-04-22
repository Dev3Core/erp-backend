import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser, require_roles
from app.core.html_sanitizer import sanitize_bio_html
from app.core.pagination import OffsetPage, OffsetParams, build_offset_page, offset_params
from app.core.tenant import CurrentTenantId
from app.database import get_db
from app.models.user import Role
from app.schemas.bio_template import (
    BioSanitizeRequest,
    BioSanitizeResponse,
    BioTemplateCreate,
    BioTemplateResponse,
    BioTemplateUpdate,
)
from app.services.bio_template import BioTemplateService
from app.services.errors import ServiceError

router = APIRouter(prefix="/bio-templates", tags=["bio-templates"])

MonitorUp = require_roles(Role.OWNER, Role.ADMIN, Role.MONITOR)
AnyAuthed = require_roles(Role.OWNER, Role.ADMIN, Role.MONITOR, Role.MODEL)


def _get_service(db: Annotated[AsyncSession, Depends(get_db)]) -> BioTemplateService:
    return BioTemplateService(db)


ServiceDep = Annotated[BioTemplateService, Depends(_get_service)]


@router.post(
    "",
    response_model=BioTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[MonitorUp],
)
async def create_template(
    body: BioTemplateCreate,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    svc: ServiceDep,
):
    return await svc.create(
        tenant_id=tenant_id,
        created_by=user.id,
        name=body.name,
        html_content=body.html_content,
    )


@router.get("", response_model=OffsetPage[BioTemplateResponse], dependencies=[AnyAuthed])
async def list_templates(
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
    params: Annotated[OffsetParams, Depends(offset_params)],
    active_only: Annotated[bool, Query()] = False,
):
    items, total = await svc.list(tenant_id=tenant_id, params=params, active_only=active_only)
    return build_offset_page([BioTemplateResponse.model_validate(x) for x in items], total, params)


@router.get("/{template_id}", response_model=BioTemplateResponse, dependencies=[AnyAuthed])
async def get_template(
    template_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
):
    try:
        return await svc.get(tenant_id=tenant_id, template_id=template_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None


@router.patch("/{template_id}", response_model=BioTemplateResponse, dependencies=[MonitorUp])
async def update_template(
    template_id: uuid.UUID,
    body: BioTemplateUpdate,
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
):
    try:
        return await svc.update(
            tenant_id=tenant_id,
            template_id=template_id,
            name=body.name,
            html_content=body.html_content,
            is_active=body.is_active,
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[MonitorUp])
async def delete_template(
    template_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    svc: ServiceDep,
):
    try:
        await svc.delete(tenant_id=tenant_id, template_id=template_id)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None
    return None


@router.post(
    "/sanitize",
    response_model=BioSanitizeResponse,
    dependencies=[AnyAuthed],
)
async def sanitize_html(body: BioSanitizeRequest):
    """Utility endpoint: returns the sanitized HTML that would be stored if you
    created a template with this content. Useful for a live preview in the UI."""
    cleaned = sanitize_bio_html(body.html_content)
    return BioSanitizeResponse(
        original_length=len(body.html_content),
        sanitized_length=len(cleaned),
        html_content=cleaned,
    )
