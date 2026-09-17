from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env", extra="ignore"
    )
    database_url: str
    jwt_secret: str
    admin_email: str = "admin@example.com"
    admin_password: str
    storage_dir: str = "./storage"
    cors_origins: str = "http://localhost:3000"
    cookie_secure: bool = False
    ai_api_key: str = ""
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-4.1-mini"
    max_upload_mb: int = 10


@lru_cache
def settings():
    value = Settings()
    if (
        len(value.jwt_secret) < 32
        or len(value.admin_password) < 12
        or value.jwt_secret.startswith("replace-")
        or value.admin_password.startswith("replace-")
    ):
        raise ValueError(
            "JWT_SECRET must have 32+ characters and ADMIN_PASSWORD 12+ characters"
        )
    return value
