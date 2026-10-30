"""Application configuration.

Settings are read from environment variables, which docker-compose supplies
from the .env file. Nothing secret is hard-coded here.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Connection string for PostgreSQL, e.g.
    # postgresql+psycopg://user:password@db:5432/safemed
    DATABASE_URL: str

    # Connection string for Redis (used by the background worker later).
    REDIS_URL: str = "redis://redis:6379/0"

    ENVIRONMENT: str = "development"

    PROJECT_NAME: str = "SafeMed"
    API_V1_PREFIX: str = "/api/v1"


# A single shared instance, imported wherever configuration is needed.
settings = Settings()
