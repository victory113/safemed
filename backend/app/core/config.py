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

    # Secret used to sign login tokens (JWTs). No default on purpose: if it
    # is missing the app refuses to start instead of running with a weak key.
    SECRET_KEY: str

    # How long a login token stays valid, in seconds (the API contract says 3600).
    ACCESS_TOKEN_EXPIRE_SECONDS: int = 3600

    PROJECT_NAME: str = "SafeMed"
    API_V1_PREFIX: str = "/api/v1"


# A single shared instance, imported wherever configuration is needed.
settings = Settings()