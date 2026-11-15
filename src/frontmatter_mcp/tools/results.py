"""Shapes of the tool results (published to clients as output schemas)."""

from typing import Any

from typing_extensions import NotRequired, TypedDict

from frontmatter_mcp.records import FileWarning


class QueryInspectResult(TypedDict):
    file_count: int
    schema: dict[str, Any]
    warnings: NotRequired[list[FileWarning]]


class QueryResult(TypedDict):
    results: list[dict[str, Any]]
    row_count: int
    columns: list[str]
    warnings: NotRequired[list[FileWarning]]


class UpdateResult(TypedDict):
    path: str
    frontmatter: dict[str, Any]
    updated: bool  # False when the values were already as requested


class BatchResult(TypedDict):
    updated_count: int
    updated_files: list[str]
    warnings: NotRequired[list[FileWarning]]


class IndexRun(TypedDict):
    indexed: int
    removed: int
    failed: int
    error: str | None


class IndexStatus(TypedDict):
    state: str
    has_index: bool
    last_run: IndexRun | None


class IndexWaitResult(IndexStatus):
    success: bool


class IndexRefreshResult(TypedDict):
    state: str
    message: str
    target_count: NotRequired[int]


class SearchHitResult(TypedDict):
    path: str
    line: int
    heading: str
    section: list[str]
    text: str
    score: float


class SearchResult(TypedDict):
    results: list[SearchHitResult]
    index: IndexStatus
    warnings: NotRequired[list[FileWarning]]
