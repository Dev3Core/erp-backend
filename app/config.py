from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    APP_NAME: str = "ERP Webcam API"
    DEBUG: bool = False

    DATABASE_URL: str = "postgresql+asyncpg://erp:erp_local@localhost:5432/erp_webcam"
    REDIS_URL: str = "redis://localhost:6379"

    JWT_SECRET: SecretStr = Field(..., min_length=64)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_MINUTES: int = 15
    JWT_REFRESH_EXPIRES_MINUTES: int = 10080  # 7 days

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    SESSION_COOKIE_SECURE: bool = False  # MUST be True in production (HTTPS)

    @field_validator("JWT_SECRET")
    @classmethod
    def _reject_placeholder(cls, v: SecretStr) -> SecretStr:
        s = v.get_secret_value()
        if "change-me" in s.lower() or s.lower().startswith("secret"):
            raise ValueError("JWT_SECRET must not be a placeholder")
        return v


settings = Settings()
