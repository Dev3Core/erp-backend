from datetime import UTC, datetime, timedelta
from enum import StrEnum

from argon2 import PasswordHasher
from jose import JWTError, jwt

from app.config import settings

_hasher = PasswordHasher()


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except Exception:
        return False


def _create_token(data: dict[str, object], expires_delta: timedelta, token_type: TokenType) -> str:
    to_encode = {**data, "type": token_type.value}
    to_encode["exp"] = datetime.now(UTC) + expires_delta
    return jwt.encode(
        to_encode,
        settings.JWT_SECRET.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )


def create_access_token(data: dict[str, object]) -> str:
    return _create_token(data, timedelta(minutes=settings.JWT_EXPIRES_MINUTES), TokenType.ACCESS)


def create_refresh_token(data: dict[str, object]) -> str:
    return _create_token(
        data, timedelta(minutes=settings.JWT_REFRESH_EXPIRES_MINUTES), TokenType.REFRESH
    )


def decode_token(token: str) -> dict[str, object]:
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError:
        raise


def token_blacklist_key(jti: str) -> str:
    return f"token:blacklist:{jti}"
