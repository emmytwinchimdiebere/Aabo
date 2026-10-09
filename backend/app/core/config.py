import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = PROJECT_ROOT / "backend"
DEFAULT_PHONE_HASH_SALT = "local-development-only"

load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str
    base_url: str
    database_path: Path
    phone_hash_salt: str
    cors_origins: tuple[str, ...]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    def validate(self) -> None:
        if self.is_production and self.phone_hash_salt == DEFAULT_PHONE_HASH_SALT:
            raise RuntimeError("PHONE_HASH_SALT must be configured in production")
        if self.is_production and not self.base_url.startswith("https://"):
            raise RuntimeError("BASE_URL must use HTTPS in production")


def _database_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (BACKEND_ROOT / path).resolve()


def _cors_origins(value: str) -> tuple[str, ...]:
    return tuple(origin.strip() for origin in value.split(",") if origin.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings(
        environment=os.getenv("APP_ENV", "development"),
        base_url=os.getenv("BASE_URL", "http://localhost:8000").rstrip("/"),
        database_path=_database_path(os.getenv("DATABASE_PATH", "./data/aabo112.db")),
        phone_hash_salt=os.getenv("PHONE_HASH_SALT", DEFAULT_PHONE_HASH_SALT),
        cors_origins=_cors_origins(os.getenv("CORS_ORIGINS", "http://localhost:5173")),
    )
