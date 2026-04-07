from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser
from app.database import get_db
from app.redis import get_redis
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    MFASetupResponse,
    MFAVerifyRequest,
    MFAVerifyResponse,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from app.services.auth import AuthError, AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_auth_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> AuthService:
    return AuthService(db, redis)


AuthServiceDep = Annotated[AuthService, Depends(_get_auth_service)]

_COOKIE_OPTS: dict = {
    "httponly": True,
    "samesite": "lax",
    "secure": False,  # True in production behind HTTPS
    "path": "/",
}


def _set_tokens(response: Response, access: str, refresh: str) -> None:
    response.set_cookie("access_token", access, max_age=15 * 60, **_COOKIE_OPTS)
    response.set_cookie("refresh_token", refresh, max_age=7 * 24 * 3600, **_COOKIE_OPTS)


def _clear_tokens(response: Response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, svc: AuthServiceDep):
    try:
        tenant, owner = await svc.register(
            studio_name=body.studio_name,
            full_name=body.full_name,
            email=body.email,
            password=body.password,
        )
    except AuthError as e:
        raise HTTPException(e.status_code, e.detail) from None

    return RegisterResponse(
        tenant_id=tenant.id,
        user_id=owner.id,
        email=owner.email,
        studio_slug=tenant.slug,
    )


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, response: Response, svc: AuthServiceDep):
    try:
        user = await svc.authenticate(body.email, body.password)
    except AuthError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, e.detail) from None

    mfa_required = user.mfa_enabled
    access, refresh = svc.create_token_pair(user, mfa_verified=not mfa_required)
    _set_tokens(response, access, refresh)

    return LoginResponse(
        user_id=user.id,
        email=user.email,
        role=user.role.value,
        mfa_required=mfa_required,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    svc: AuthServiceDep,
    refresh_token: Annotated[str | None, Cookie()] = None,
):
    if refresh_token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No refresh token")

    try:
        access, new_refresh, _ = await svc.refresh_tokens(refresh_token)
    except AuthError as e:
        _clear_tokens(response)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, e.detail) from None

    _set_tokens(response, access, new_refresh)
    return TokenResponse()


@router.post("/logout", response_model=TokenResponse)
async def logout(
    response: Response,
    svc: AuthServiceDep,
    access_token: Annotated[str | None, Cookie()] = None,
    refresh_token: Annotated[str | None, Cookie()] = None,
):
    if access_token:
        await svc.logout(access_token, refresh_token)
    _clear_tokens(response)
    return TokenResponse(detail="Logged out")


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def mfa_setup(user: CurrentUser, svc: AuthServiceDep):
    try:
        uri, secret = await svc.setup_mfa(user)
    except AuthError as e:
        raise HTTPException(e.status_code, e.detail) from None

    return MFASetupResponse(qr_uri=uri, secret=secret)


@router.post("/mfa/verify", response_model=MFAVerifyResponse)
async def mfa_verify(
    body: MFAVerifyRequest,
    response: Response,
    user: CurrentUser,
    svc: AuthServiceDep,
):
    try:
        await svc.verify_mfa(user, body.code)
    except AuthError as e:
        raise HTTPException(e.status_code, e.detail) from None

    access, refresh = svc.create_token_pair(user, mfa_verified=True)
    _set_tokens(response, access, refresh)
    return MFAVerifyResponse()
