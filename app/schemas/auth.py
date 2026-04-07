import uuid

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    studio_name: str = Field(min_length=2, max_length=255)
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RegisterResponse(BaseModel):
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    studio_slug: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    role: str
    mfa_required: bool


class TokenResponse(BaseModel):
    detail: str = "ok"


class MFASetupResponse(BaseModel):
    qr_uri: str
    secret: str


class MFAVerifyRequest(BaseModel):
    code: str


class MFAVerifyResponse(BaseModel):
    detail: str = "MFA activated"


class UserPayload(BaseModel):
    sub: str
    tenant_id: str
    role: str
    mfa_verified: bool
