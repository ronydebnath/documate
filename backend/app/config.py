"""DocuMate runtime settings.

Reads from environment, falling back to .env in the repo root. Use
`get_settings()` everywhere; the result is cached so the model name and
Chroma path don't have to be threaded through call sites.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM (Anthropic)
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_generator_model: str = Field(
        default="claude-sonnet-4-6", alias="ANTHROPIC_GENERATOR_MODEL"
    )
    anthropic_judge_model: str = Field(
        default="claude-haiku-4-5-20251001", alias="ANTHROPIC_JUDGE_MODEL"
    )

    # Embeddings (local sentence-transformers)
    embedding_model: str = Field(
        default="BAAI/bge-small-en-v1.5", alias="EMBEDDING_MODEL"
    )
    embedding_device: str = Field(default="cpu", alias="EMBEDDING_DEVICE")

    # Vector store
    chroma_persist_dir: str = Field(
        default=str(REPO_ROOT / "data" / "chroma"), alias="CHROMA_PERSIST_DIR"
    )
    chroma_collection: str = Field(default="fairwork", alias="CHROMA_COLLECTION")

    # Retrieval
    retrieval_top_k: int = Field(default=5, alias="RETRIEVAL_TOP_K")
    reranker_enabled: bool = Field(default=False, alias="RERANKER_ENABLED")

    # API
    backend_host: str = Field(default="0.0.0.0", alias="BACKEND_HOST")
    backend_port: int = Field(default=8000, alias="BACKEND_PORT")
    cors_allowed_origins: str = Field(
        default="http://localhost:3000", alias="CORS_ALLOWED_ORIGINS"
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
