"""Settings module for frontmatter-mcp."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Default cache directory name
DEFAULT_CACHE_DIR_NAME = ".frontmatter-mcp"

# Default embedding model
DEFAULT_EMBEDDING_MODEL = "cl-nagoya/ruri-v3-30m"


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Environment variables:
        FRONTMATTER_BASE_DIR: Base directory path (required)
        FRONTMATTER_ENABLE_SEMANTIC: Enable semantic search (default: false)
        FRONTMATTER_EMBEDDING_MODEL: Embedding model name (default: auto)
        FRONTMATTER_CACHE_DIR: Cache directory path (default: base_dir/.frontmatter-mcp)
    """

    model_config = SettingsConfigDict(env_prefix="FRONTMATTER_")

    base_dir: Path
    enable_semantic: bool = False
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    cache_dir: Path | None = None

    def get_cache_dir(self, base_dir: Path) -> Path:
        """Get the cache directory path.

        Args:
            base_dir: Base directory for default cache location.

        Returns:
            Cache directory path from settings, or base_dir/.frontmatter-mcp if not set.
        """
        if self.cache_dir:
            return self.cache_dir
        return base_dir / DEFAULT_CACHE_DIR_NAME


@lru_cache
def get_settings() -> Settings:
    """Get the cached settings instance.

    Settings are read from environment variables on first call and cached.
    Use get_settings.cache_clear() in tests to reset.

    Returns:
        Cached Settings instance.

    Raises:
        ValidationError: If required environment variables are not set.
    """
    return Settings()
