"""Settings module for frontmatter-mcp."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Default cache directory name
DEFAULT_CACHE_DIR_NAME = ".frontmatter-mcp"


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Environment variables:
        FRONTMATTER_ENABLE_SEMANTIC: Enable semantic search (default: false)
        FRONTMATTER_EMBEDDING_MODEL: Embedding model name (default: auto)
        FRONTMATTER_CACHE_DIR: Cache directory path (default: base_dir/.frontmatter-mcp)
    """

    model_config = SettingsConfigDict(env_prefix="FRONTMATTER_")

    enable_semantic: bool = False
    embedding_model: str | None = None
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


# Global settings instance (read-only after creation)
settings = Settings()
