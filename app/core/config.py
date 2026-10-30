from __future__ import annotations

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# <root>/app/core/config.py -> parents[0]=core, parents[1]=app, parents[2]=<root>
ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",               # unknown keys in .env are not an error
    )

    # --- Embeddings / LLM provider ---------------------------------------------
    embedding_model: str = "text-embedding-3-small"
    openai_api_key: str | None = None  # optional here; can also come from the OS environment

    # --- Storage ---------------------------------------------------------------
    vector_dir: str = "./data/vectorstore"      # relative paths are anchored to ROOT_DIR
    registry_db: str = "./data/sources.db"      # source registry (list_sources / chunk counts)
    redis_url: str = "redis://localhost:6379/0"

    # --- Ingestion -------------------------------------------------------------
    max_upload_mb: int = 25
    chunk_size: int = 1000
    chunk_overlap: int = 150
    whisper_model: str = "small"

    # --- Cache -----------------------------------------------------------------
    answer_cache_ttl: int = 3600                # seconds (used by the chat side)

    # --- Logging ---------------------------------------------------------------
    log_level: str = "INFO"

    @model_validator(mode="after")
    def _check_chunking(self) -> "Settings":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self

    # --- Derived values --------------------------------------------------------
    @property
    def vector_path(self) -> Path:
        """Absolute path of the Chroma folder (an absolute vector_dir is kept as is)."""
        return (ROOT_DIR / self.vector_dir).resolve()

    @property
    def registry_path(self) -> Path:
        return (ROOT_DIR / self.registry_db).resolve()

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


settings = Settings()