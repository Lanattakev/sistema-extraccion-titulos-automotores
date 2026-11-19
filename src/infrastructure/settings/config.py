"""src/infrastructure/settings/config.py — Centralización de variables de entorno."""

from __future__ import annotations

import os
import shutil
import sys
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_tesseract_command() -> str:
    if sys.platform == "win32":
        return r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    return shutil.which("tesseract") or "tesseract"


def batch_cpu_limit() -> int:
    """Reserva un CPU y respeta afinidad cuando el sistema la expone."""
    count = os.cpu_count() or 1
    process_count = getattr(os, "process_cpu_count", None)
    if process_count is not None:
        count = min(count, process_count() or 1)
    affinity = getattr(os, "sched_getaffinity", None)
    if affinity is not None:
        try:
            count = min(count, len(affinity(0)))
        except OSError:
            pass
    return max(1, min(4, count - 1))


def initialize_batch_worker() -> None:
    """Solo en hijos spawn: evita multiplicar hilos OpenMP por cada Tesseract."""
    os.environ["OMP_THREAD_LIMIT"] = "1"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Entorno
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=False)
    LOG_LEVEL: str = Field(default="INFO")

    # API
    PROJECT_NAME: str = Field(default="backend-api")
    VERSION: str = Field(default="1.0.0")
    API_V1_PREFIX: str = Field(default="/api/v1")
    ALLOWED_HOSTS: list[str] = Field(default_factory=lambda: ["*"])

    # Seguridad
    SECRET_KEY: str = Field(default="change-this-insecure-secret-key-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60)

    # Base de Datos
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./app.db")
    SQLITE_POOL_SIZE: int = Field(default=4, gt=0)

    # Lotes: reserva estimada de 256 MiB por proceso, no limite RSS del SO.
    BATCH_MAX_WORKERS: int = Field(default_factory=batch_cpu_limit, ge=1, le=4)
    BATCH_MEMORY_BUDGET_MB: int = Field(default=1024, ge=256)

    # OCR local
    TESSERACT_CMD: str = Field(default_factory=default_tesseract_command)
    TESSERACT_LANG: str = Field(default="spa+eng")
    TESSERACT_TIMEOUT: int = Field(default=30, gt=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
