"""Application settings loaded from FRONTMATTER_* environment variables."""

from pathlib import Path
from typing import Annotated, Any

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEFAULT_CACHE_DIR_NAME = ".frontmatter-mcp"
DEFAULT_EMBEDDING_MODEL = "cl-nagoya/ruri-v3-30m"
DEFAULT_RERANKER_MODEL = "hotchpotch/japanese-reranker-xsmall-v2"


class Settings(BaseSettings):
    """Application settings.

    Each field is read from the environment variable FRONTMATTER_<FIELD>
    (for example FRONTMATTER_BASE_DIR).
    """

    model_config = SettingsConfigDict(env_prefix="FRONTMATTER_")

    # Directory whose Markdown files are served (resolved, must exist)
    base_dir: Path
    # Globs relative to base_dir that no tool reads, writes or indexes.
    # Comma-separated in the environment: "IDENTITY.md,_templates"
    exclude: Annotated[list[str], NoDecode] = []
    enable_semantic: bool = False
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    # None uses the model's recommended prefixes (set for ruri-v3)
    embedding_query_prefix: str | None = None
    embedding_document_prefix: str | None = None
    # Cross-encoder for the search tool; empty string turns reranking off
    reranker_model: str = DEFAULT_RERANKER_MODEL
    # Where the semantic index is stored; relative paths are under base_dir.
    # Defaults to base_dir/.frontmatter-mcp
    cache_dir: Path = Path(DEFAULT_CACHE_DIR_NAME)

    @field_validator("base_dir")
    @classmethod
    def _resolve_base_dir(cls, value: Path) -> Path:
        resolved = value.expanduser().resolve()
        if not resolved.is_dir():
            raise ValueError(f"Base directory does not exist: {resolved}")
        return resolved

    @field_validator("exclude", mode="before")
    @classmethod
    def _split_exclude(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.split(",")
        if isinstance(value, list):
            return [str(p).strip() for p in value if str(p).strip()]
        return value

    @model_validator(mode="after")
    def _resolve_cache_dir(self) -> "Settings":
        cache_dir = self.cache_dir.expanduser()
        if not cache_dir.is_absolute():
            cache_dir = self.base_dir / cache_dir
        self.cache_dir = cache_dir.resolve()
        return self
