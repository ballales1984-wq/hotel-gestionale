"""
Hotel ABC Platform — Configuration
Centralized settings with environment variable support.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ────────────────────────────────────────────────────────────────
    app_name: str = "Hotel ABC Platform"
    app_version: str = "0.1.0"
    environment: str = Field("development", env="ENVIRONMENT")
    log_level: str = Field("info", env="LOG_LEVEL")
    debug: bool = Field(False, env="DEBUG")

    # ── Database ────────────────────────────────────────────────────────────
    database_url: str = Field(
        "sqlite+aiosqlite:///./hotel_abc.db",
        env="DATABASE_URL",
    )
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # ── Redis ───────────────────────────────────────────────────────────────
    redis_url: str = Field(
        "redis://localhost:6379/0",
        env="REDIS_URL",
    )
    cache_ttl_seconds: int = 3600  # 1 ora default

    # ── Security ────────────────────────────────────────────────────────────
    secret_key: str = Field("change_me_in_production", env="SECRET_KEY")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480  # 8 ore (turno lavoro)

    # ── CORS ────────────────────────────────────────────────────────────────
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8088"]

    # ── File Upload ─────────────────────────────────────────────────────────
    upload_dir: str = Field("../data/uploads", env="UPLOAD_DIR")
    max_upload_size_mb: int = 50
    allowed_extensions: List[str] = [".csv", ".xlsx", ".xls"]

    # ── DuckDB ──────────────────────────────────────────────────────────────
    duckdb_path: str = Field("../data/duckdb/analytics.db", env="DUCKDB_PATH")

    # ── ABC Engine ──────────────────────────────────────────────────────────
    abc_max_iterations: int = 10        # max iterazioni ribaltamenti circolari
    abc_convergence_threshold: float = 0.001  # soglia convergenza


@lru_cache()
def get_settings() -> Settings:
    return Settings()
