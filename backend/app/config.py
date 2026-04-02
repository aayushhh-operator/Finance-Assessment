from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    api_v1_prefix: str = "/api"
    project_name: str = "Finance Backend API"


@lru_cache
def get_settings() -> Settings:
    return Settings()
