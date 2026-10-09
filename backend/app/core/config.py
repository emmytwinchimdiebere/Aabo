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
    recording_allowed_hosts: tuple[str, ...]
    recording_max_bytes: int
    recording_timeout_seconds: float
    hf_token: str | None
    hf_inference_base_url: str
    natlas_asr_model: str
    fallback_asr_model: str
    transcription_timeout_seconds: float

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    def validate(self) -> None:
        if self.recording_max_bytes <= 0:
            raise RuntimeError("RECORDING_MAX_BYTES must be greater than zero")
        if self.recording_timeout_seconds <= 0:
            raise RuntimeError("RECORDING_TIMEOUT_SECONDS must be greater than zero")
        if self.transcription_timeout_seconds <= 0:
            raise RuntimeError("TRANSCRIPTION_TIMEOUT_SECONDS must be greater than zero")
        if self.is_production and self.phone_hash_salt == DEFAULT_PHONE_HASH_SALT:
            raise RuntimeError("PHONE_HASH_SALT must be configured in production")
        if self.is_production and not self.base_url.startswith("https://"):
            raise RuntimeError("BASE_URL must use HTTPS in production")
        if self.is_production and not self.recording_allowed_hosts:
            raise RuntimeError("AT_RECORDING_ALLOWED_HOSTS must be configured in production")


def _database_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (BACKEND_ROOT / path).resolve()


def _csv_values(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings(
        environment=os.getenv("APP_ENV", "development"),
        base_url=os.getenv("BASE_URL", "http://localhost:8000").rstrip("/"),
        database_path=_database_path(os.getenv("DATABASE_PATH", "./data/aabo112.db")),
        phone_hash_salt=os.getenv("PHONE_HASH_SALT", DEFAULT_PHONE_HASH_SALT),
        cors_origins=_csv_values(os.getenv("CORS_ORIGINS", "http://localhost:5173")),
        recording_allowed_hosts=_csv_values(os.getenv("AT_RECORDING_ALLOWED_HOSTS", "")),
        recording_max_bytes=int(os.getenv("RECORDING_MAX_BYTES", "10485760")),
        recording_timeout_seconds=float(os.getenv("RECORDING_TIMEOUT_SECONDS", "15")),
        hf_token=os.getenv("HF_TOKEN") or None,
        hf_inference_base_url=os.getenv(
            "HF_INFERENCE_BASE_URL",
            "https://router.huggingface.co/hf-inference/models",
        ).rstrip("/"),
        natlas_asr_model=os.getenv("NATLAS_ASR_MODEL", "NCAIR1/NigerianAccentedEnglish"),
        fallback_asr_model=os.getenv("FALLBACK_ASR_MODEL", "openai/whisper-large-v3"),
        transcription_timeout_seconds=float(os.getenv("TRANSCRIPTION_TIMEOUT_SECONDS", "45")),
    )
