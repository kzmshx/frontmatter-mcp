"""Dependency injection for FastMCP tools.

This module provides singleton-cached dependencies for use with FastMCP's
Depends system. Each dependency is instantiated once on first use and
cached for the lifetime of the application.
"""

from frontmatter_mcp.files import FileRecordCache
from frontmatter_mcp.semantic import SemanticContext, get_semantic_context
from frontmatter_mcp.settings import Settings
from frontmatter_mcp.settings import get_settings as _get_settings

# Singleton caches
_settings_cache: Settings | None = None
_semantic_ctx_cache: SemanticContext | None = None
_file_record_cache_instance: FileRecordCache | None = None


def get_settings() -> Settings:
    """Get application settings (singleton)."""
    global _settings_cache
    if _settings_cache is None:
        _settings_cache = _get_settings()
    return _settings_cache


def get_file_record_cache() -> FileRecordCache:
    """Get file record cache (singleton)."""
    global _file_record_cache_instance
    if _file_record_cache_instance is None:
        _file_record_cache_instance = FileRecordCache()
    return _file_record_cache_instance


def get_semantic_ctx() -> SemanticContext | None:
    """Get semantic context if enabled (singleton).

    Returns None if semantic search is disabled.
    """
    global _semantic_ctx_cache
    settings = get_settings()
    if not settings.enable_semantic:
        return None
    if _semantic_ctx_cache is None:
        _semantic_ctx_cache = get_semantic_context(settings)
    return _semantic_ctx_cache


def reset_caches() -> None:
    """Reset all singleton caches. Useful for testing."""
    global _settings_cache, _semantic_ctx_cache, _file_record_cache_instance
    _settings_cache = None
    _semantic_ctx_cache = None
    _file_record_cache_instance = None
