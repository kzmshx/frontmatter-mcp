"""Semantic search tools: search, index_status, index_wait, index_refresh.

Registered with the semantic tag; the server shows them only when semantic
search is enabled and its packages are installed.
"""

from typing import cast

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError

from frontmatter_mcp.app import READ_ONLY, SEMANTIC_TAG, mcp
from frontmatter_mcp.dependencies import (
    get_file_record_cache,
    get_semantic_ctx,
    get_settings,
)
from frontmatter_mcp.paths import collect_files, relative
from frontmatter_mcp.records import FileRecordCache, FileWarning, parse_files
from frontmatter_mcp.semantic import SemanticContext
from frontmatter_mcp.settings import Settings
from frontmatter_mcp.sql import create_files_connection
from frontmatter_mcp.tools.query import INDEX_WAIT_SECONDS, run_sql
from frontmatter_mcp.tools.results import (
    IndexRefreshResult,
    IndexStatus,
    IndexWaitResult,
    SearchHitResult,
    SearchResult,
)

MAX_SEARCH_LIMIT = 50


def _require(semantic_ctx: SemanticContext | None) -> SemanticContext:
    if semantic_ctx is None:
        raise ToolError(
            "Semantic search is disabled. Set FRONTMATTER_ENABLE_SEMANTIC=true "
            "and install frontmatter-mcp[semantic]."
        )
    return semantic_ctx


def _status(semantic_ctx: SemanticContext) -> IndexStatus:
    return cast(IndexStatus, semantic_ctx.status())


@mcp.tool(tags={SEMANTIC_TAG}, annotations=READ_ONLY)
def search(
    query: str,
    glob: str = "**/*.md",
    where: str | None = None,
    limit: int = 10,
    exclude_sections: list[str] | None = None,
    settings: Settings = Depends(get_settings),
    cache: FileRecordCache = Depends(get_file_record_cache),
    semantic_ctx: SemanticContext | None = Depends(get_semantic_ctx),
) -> SearchResult:
    """Search document text and return the best-matching passage of each document.

    Combines meaning (embeddings of ~400-character chunks) with wording
    (character-bigram BM25), and reranks the candidates with a cross-encoder
    unless reranking is turned off. Works for paraphrases ("felt lonely on my
    birthday") as well as exact names. Use the returned path and line to read
    more of a document.

    Args:
        query: What to look for, as a sentence or keywords.
        glob: Glob pattern relative to base directory to search within.
        where: Optional SQL condition on frontmatter to restrict documents, using
            the same columns as the query tool. Examples:
            "date < '2026-11-01'", "path LIKE 'daily/%'",
            "list_contains(from_json(tags, '[\\"VARCHAR\\"]'), 'record/daily')".
        limit: Maximum number of documents to return (1-50). Default 10.
        exclude_sections: Headings to leave out: a passage under any of them,
            at any level, is not matched (e.g. ["AI comments"] to skip a
            section other people or tools write in every note).

    Returns:
        Dict with results (path, line, heading, section, text, score; best
        first; section is the heading path from the top level down to
        heading) and
        index (state, whether an index exists, last run statistics and
        error). Scores are only comparable within one search. The first
        search in a session brings the index up to date (usually seconds); if
        the state is still "indexing", results cover what was indexed so far.
    """
    semantic_ctx = _require(semantic_ctx)
    semantic_ctx.ensure_index(wait_seconds=INDEX_WAIT_SECONDS)
    limit = max(1, min(limit, MAX_SEARCH_LIMIT))
    base_dir = settings.base_dir
    paths = collect_files(base_dir, glob)
    allowed = {relative(base_dir, p) for p in paths}
    warnings: list[FileWarning] = []
    if where:
        records, warnings = parse_files(paths, base_dir, cache)
        conn = create_files_connection(records)
        rows = run_sql(conn, f"SELECT path FROM files WHERE {where}")
        allowed &= {r["path"] for r in rows["results"]}

    hits = (
        semantic_ctx.search(
            query,
            limit,
            allowed_paths=allowed,
            exclude_sections=exclude_sections or (),
        )
        if allowed
        else []
    )
    result = SearchResult(
        results=[cast(SearchHitResult, h.to_dict()) for h in hits],
        index=_status(semantic_ctx),
    )
    if warnings:
        result["warnings"] = warnings
    return result


@mcp.tool(tags={SEMANTIC_TAG}, annotations=READ_ONLY)
def index_status(
    semantic_ctx: SemanticContext | None = Depends(get_semantic_ctx),
) -> IndexStatus:
    """Get the status of the semantic search index.

    Returns:
        Dict with:
        - state: "idle" (not started in this session; the first search starts
          it), "indexing" (a run is in progress), or "ready"
        - has_index: whether an index is being served (a run has finished,
          or a search has loaded what is on disk). Stays true during a
          refresh, which serves the previous index
        - last_run: files indexed, removed, and failed in the last finished
          run, and the error that stopped it, if any
    """
    return _status(_require(semantic_ctx))


@mcp.tool(tags={SEMANTIC_TAG}, annotations=READ_ONLY)
def index_wait(
    timeout: float = 60.0,
    semantic_ctx: SemanticContext | None = Depends(get_semantic_ctx),
) -> IndexWaitResult:
    """Wait for semantic search indexing to complete.

    Blocks until indexing finishes or timeout is reached.
    Use this instead of polling index_status when you need embeddings.

    Args:
        timeout: Maximum seconds to wait. Default 60.

    Returns:
        Dict with success and the fields of index_status.
        - success=true: no run in progress (finished, or never started)
        - success=false: timeout reached while indexing is in progress
    """
    semantic_ctx = _require(semantic_ctx)
    completed = semantic_ctx.wait(timeout)
    return cast(IndexWaitResult, {"success": completed, **_status(semantic_ctx)})


@mcp.tool(tags={SEMANTIC_TAG})
def index_refresh(
    semantic_ctx: SemanticContext | None = Depends(get_semantic_ctx),
) -> IndexRefreshResult:
    """Refresh the semantic search index (differential update).

    Starts background indexing. Only files changed since the last run (by
    mtime) are re-read; on the first run every file is indexed.

    If indexing is already in progress, returns current status.

    Returns:
        Dict with state, message, and target_count (files found).

    Notes:
        Call this after editing files during a session to update the index.
    """
    return cast(IndexRefreshResult, _require(semantic_ctx).refresh())
