"""Application state shared by the tools, exposed through FastMCP Depends.

The state is created once, on first use: settings from the environment, the
frontmatter record cache, and (when enabled) the semantic search context.
Tests replace it with set_state() or clear it with reset_state().
"""

import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from frontmatter_mcp.records import FileRecordCache
from frontmatter_mcp.settings import Settings

if TYPE_CHECKING:
    from frontmatter_mcp.semantic import SemanticContext


@dataclass
class AppState:
    """Everything the tools share for the lifetime of the server."""

    settings: Settings
    file_cache: FileRecordCache = field(default_factory=FileRecordCache)
    _semantic: "SemanticContext | None" = None
    _semantic_lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def semantic(self) -> "SemanticContext | None":
        """Semantic search context, created on first use; None when disabled."""
        if not self.settings.enable_semantic:
            return None
        with self._semantic_lock:
            if self._semantic is None:
                from frontmatter_mcp.semantic import create_semantic_context

                self._semantic = create_semantic_context(self.settings)
            return self._semantic


_state: AppState | None = None
_state_lock = threading.Lock()


def get_state() -> AppState:
    """The application state, created from the environment on first use."""
    global _state
    with _state_lock:
        if _state is None:
            _state = AppState(settings=Settings())  # type: ignore[call-arg]
        return _state


def set_state(state: AppState | None) -> None:
    """Replace the application state (tests)."""
    global _state
    with _state_lock:
        _state = state


def reset_state() -> None:
    """Drop the application state; the next call rebuilds it (tests)."""
    set_state(None)


def get_settings() -> Settings:
    return get_state().settings


def get_file_record_cache() -> FileRecordCache:
    return get_state().file_cache


def get_semantic_ctx() -> "SemanticContext | None":
    return get_state().semantic
