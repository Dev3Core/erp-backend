import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser, require_roles
from app.core.security import TokenType, decode_token
from app.core.tenant import CurrentTenantId
from app.core.ws_hub import hub
from app.database import async_session, get_db
from app.models.user import Role, User
from app.schemas.chat import ChatMessageListResponse, ChatMessageResponse, ChatSend
from app.services.chat import ChatService
from app.services.errors import ServiceError

router = APIRouter(prefix="/chat", tags=["chat"])

AnyAuthed = require_roles(Role.OWNER, Role.ADMIN, Role.MONITOR, Role.MODEL)


def _get_service(db: Annotated[AsyncSession, Depends(get_db)]) -> ChatService:
    return ChatService(db)


ServiceDep = Annotated[ChatService, Depends(_get_service)]


@router.get(
    "/shift/{shift_id}/messages",
    response_model=ChatMessageListResponse,
    dependencies=[AnyAuthed],
)
async def list_messages(
    shift_id: uuid.UUID,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    svc: ServiceDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    try:
        items, total = await svc.list_for_shift(
            tenant_id=tenant_id,
            shift_id=shift_id,
            actor=user,
            limit=limit,
            offset=offset,
        )
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None
    return ChatMessageListResponse(
        items=[ChatMessageResponse.model_validate(x) for x in items], total=total
    )


@router.post(
    "/shift/{shift_id}/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[AnyAuthed],
)
async def send_message(
    shift_id: uuid.UUID,
    body: ChatSend,
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    svc: ServiceDep,
):
    try:
        msg = await svc.post(tenant_id=tenant_id, shift_id=shift_id, sender=user, body=body.body)
    except ServiceError as e:
        raise HTTPException(e.status_code, e.detail) from None
    resp = ChatMessageResponse.model_validate(msg)
    await hub.broadcast(
        tenant_id=tenant_id, shift_id=shift_id, payload=resp.model_dump(mode="json")
    )
    return resp


async def _ws_authenticate(access_token: str | None) -> dict | None:
    if access_token is None:
        return None
    try:
        payload = decode_token(access_token)
    except JWTError:
        return None
    if payload.get("type") != TokenType.ACCESS:
        return None
    return payload


@router.websocket("/shift/{shift_id}/ws")
async def chat_websocket(
    websocket: WebSocket,
    shift_id: uuid.UUID,
    access_token: Annotated[str | None, Cookie()] = None,
):
    """Bidirectional chat for a shift. Auth via the same `access_token` cookie
    that protects HTTP endpoints. Each incoming message is persisted and
    fanned out to every peer of the same (tenant, shift)."""
    payload = await _ws_authenticate(access_token)
    if payload is None:
        await websocket.close(code=4401)
        return

    user_id = uuid.UUID(str(payload["sub"]))
    async with async_session() as db:
        user = (
            await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
        ).scalar_one_or_none()
        if user is None:
            await websocket.close(code=4401)
            return

        svc = ChatService(db)
        try:
            await svc._ensure_participant(tenant_id=user.tenant_id, shift_id=shift_id, user=user)
        except ServiceError:
            await websocket.close(code=4403)
            return

    await websocket.accept()
    await hub.join(tenant_id=user.tenant_id, shift_id=shift_id, ws=websocket)
    try:
        while True:
            data = await websocket.receive_json()
            body = (data or {}).get("body", "")
            if not isinstance(body, str) or not body.strip():
                await websocket.send_json({"error": "body required"})
                continue
            async with async_session() as db:
                svc = ChatService(db)
                try:
                    msg = await svc.post(
                        tenant_id=user.tenant_id,
                        shift_id=shift_id,
                        sender=user,
                        body=body[:5000],
                    )
                    await db.commit()
                except ServiceError:
                    await websocket.send_json({"error": "forbidden"})
                    continue
            resp = ChatMessageResponse.model_validate(msg)
            await hub.broadcast(
                tenant_id=user.tenant_id,
                shift_id=shift_id,
                payload=resp.model_dump(mode="json"),
            )
    except WebSocketDisconnect:
        pass
    finally:
        await hub.leave(tenant_id=user.tenant_id, shift_id=shift_id, ws=websocket)
