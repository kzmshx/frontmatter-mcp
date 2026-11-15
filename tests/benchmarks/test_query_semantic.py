"""Benchmark tests for semantic search query performance."""

from pathlib import Path
from typing import Callable
from unittest.mock import MagicMock

import numpy as np
import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from frontmatter_mcp.records import FileRecordCache, parse_files
from frontmatter_mcp.semantic import add_semantic_columns
from frontmatter_mcp.semantic.context import SemanticContext
from frontmatter_mcp.semantic.store import ChunkRows
from frontmatter_mcp.sql import create_files_connection, execute_query

# Smaller file counts for semantic tests
FILE_COUNTS = [100, 500]


def _create_mock_semantic_context(paths: list[str], dim: int = 256) -> SemanticContext:
    """Create a mock SemanticContext with random embeddings."""
    embeddings = {path: np.random.rand(dim).astype(np.float32) for path in paths}

    mock_model = MagicMock()
    mock_model.get_dimension.return_value = dim
    mock_model.encode_query.return_value = np.random.rand(dim).astype(np.float32)

    sorted_paths = sorted(embeddings)
    mock_cache = MagicMock()
    mock_cache.load_chunks.return_value = ChunkRows(
        paths=sorted_paths,
        lines=np.ones(len(sorted_paths), dtype=np.int64),
        headings=[""] * len(sorted_paths),
        texts=[""] * len(sorted_paths),
        vectors=np.array([embeddings[p] for p in sorted_paths], dtype=np.float32),
    )

    mock_indexer = MagicMock()

    return SemanticContext(model=mock_model, store=mock_cache, indexer=mock_indexer)


class TestAddSemanticColumnsBenchmark:
    """Benchmark for add_semantic_columns function."""

    @pytest.mark.parametrize("file_count", FILE_COUNTS)
    def test_add_semantic_columns(
        self,
        benchmark: BenchmarkFixture,
        benchmark_dir_factory: Callable[[int], Path],
        file_count: int,
    ) -> None:
        """Measure time to add semantic columns (semantic columns + embeddings)."""
        base_dir = benchmark_dir_factory(file_count)
        paths = list(base_dir.glob("*.md"))
        records, _ = parse_files(paths, base_dir, FileRecordCache())
        relative_paths = [r["path"] for r in records]

        def setup_and_add_semantic() -> None:
            conn = create_files_connection(records)
            ctx = _create_mock_semantic_context(relative_paths)
            add_semantic_columns(conn, ctx)

        benchmark(setup_and_add_semantic)


class TestSemanticQueryBenchmark:
    """Benchmark for semantic search queries."""

    @pytest.mark.parametrize("file_count", FILE_COUNTS)
    def test_cosine_similarity_query(
        self,
        benchmark: BenchmarkFixture,
        benchmark_dir_factory: Callable[[int], Path],
        file_count: int,
    ) -> None:
        """Measure cosine similarity query time."""
        base_dir = benchmark_dir_factory(file_count)
        paths = list(base_dir.glob("*.md"))
        records, _ = parse_files(paths, base_dir, FileRecordCache())
        relative_paths = [r["path"] for r in records]

        # Setup connection with semantic columns
        conn = create_files_connection(records)
        ctx = _create_mock_semantic_context(relative_paths)
        add_semantic_columns(conn, ctx)

        sql = """
            SELECT path,
                   array_cosine_similarity(embedding, embed('test query')) as score
            FROM files
            WHERE embedding IS NOT NULL
            ORDER BY score DESC
            LIMIT 10
        """

        result = benchmark(execute_query, conn, sql)

        assert result["row_count"] <= 10
