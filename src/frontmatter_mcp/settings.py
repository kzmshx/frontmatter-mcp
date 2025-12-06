"""Application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_CACHE_DIR_NAME = ".frontmatter-mcp"
DEFAULT_EMBEDDING_MODEL = "cl-nagoya/ruri-v3-30m"


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict()

    frontmatter_base_dir: Path
    frontmatter_enable_semantic: bool = False
    frontmatter_embedding_model: str = DEFAULT_EMBEDDING_MODEL
    frontmatter_cache_dir: Path | None = None

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
    def cache_dir(self) -> Path:
        """Cache directory for embeddings database."""
        if self.frontmatter_cache_dir:
            return self.frontmatter_cache_dir
        return self.base_dir / DEFAULT_CACHE_DIR_NAME


@lru_cache
def get_settings() -> Settings:
    """Get the cached settings instance."""
    return Settings()  # type: ignore[call-arg]
