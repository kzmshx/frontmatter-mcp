"""Application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_CACHE_DIR_NAME = ".frontmatter-mcp"
DEFAULT_EMBEDDING_MODEL = "cl-nagoya/ruri-v3-30m"
DEFAULT_RERANKER_MODEL = "hotchpotch/japanese-reranker-xsmall-v2"


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict()

    frontmatter_base_dir: Path
    frontmatter_enable_semantic: bool = False
    frontmatter_embedding_model: str = DEFAULT_EMBEDDING_MODEL
    frontmatter_cache_dir: Path | None = None
    # None uses the model's recommended prefixes (set for ruri-v3)
    frontmatter_embedding_query_prefix: str | None = None
    frontmatter_embedding_document_prefix: str | None = None
    # Cross-encoder for the search tool; empty string turns reranking off
    frontmatter_reranker_model: str = DEFAULT_RERANKER_MODEL

    @property
    def base_dir(self) -> Path:
        """Base directory for markdown files."""
        base_dir = self.frontmatter_base_dir.resolve()
        if not base_dir.is_dir():
            raise RuntimeError(f"Base directory does not exist: {base_dir}")
        return base_dir

    @property
    def enable_semantic(self) -> bool:
        """Whether semantic search is enabled."""
        return self.frontmatter_enable_semantic

    @property
    def embedding_model(self) -> str:
        """Embedding model name for semantic search."""
        return self.frontmatter_embedding_model

    @property
    def reranker_model(self) -> str | None:
        """Cross-encoder model for search, or None when reranking is off."""
        return self.frontmatter_reranker_model or None

    @property
    def cache_dir(self) -> Path:
        """Cache directory for embeddings database."""
        if self.frontmatter_cache_dir:
            return self.frontmatter_cache_dir
        return self.base_dir / DEFAULT_CACHE_DIR_NAME


@lru_cache
def get_settings() -> Settings:
    """Get the cached settings instance."""
    return Settings()  # type: ignore[call-arg]
