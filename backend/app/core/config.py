"""
Application configuration, read from environment variables / .env.

ODD 1.2: provider keys and the signing secret are kept in environment
variables, never in code.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    APP_NAME: str = "Pharmacy IMS"
    API_V1_PREFIX: str = "/api/v1"
    ENV: str = "development"

    # --- Database ---
    DATABASE_URL: str = "postgresql+psycopg2://pharmacy:pharmacy@localhost:5432/pharmacy_ims"

    # --- Security / tokens ---
    # SDD 2.5 / NFR-08: signed token, 30 min inactivity timeout by default.
    JWT_SECRET_KEY: str = "CHANGE_ME_IN_ENV"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 30

    # SDD 2.7: limit on repeated failed log-ins.
    MAX_FAILED_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_MINUTES: int = 15

    # SDD 2.8: secret used by the internal job-trigger endpoint (used later
    # by the workers/reporting modules, defined here since it's a core secret).
    INTERNAL_JOB_SECRET: str = "CHANGE_ME_IN_ENV"

    # --- CORS: SDD 2.5 — "the server accepts requests only from the client address" ---
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()