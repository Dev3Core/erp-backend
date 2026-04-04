from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    APP_NAME: str = "ERP Webcam API"
    DEBUG: bool = False

    DATABASE_URL: str = "postgresql+asyncpg://erp:erp_local@localhost:5432/erp_webcam"
    REDIS_URL: str = "redis://localhost:6379"

    JWT_SECRET: str = "change-me-to-a-secure-secret-of-at-least-64-characters"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_MINUTES: int = 15

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]


settings = Settings()
