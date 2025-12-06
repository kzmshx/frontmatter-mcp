"""Benchmark tests for query performance."""

from pathlib import Path
from typing import Any, Callable

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from frontmatter_mcp.files import FileRecordCache, parse_files
from frontmatter_mcp.query import create_base_connection, execute_query

FILE_COUNTS = [100, 500, 1000]


class TestParseFilesBenchmark:
    """Benchmark for parse_files function."""

    @pytest.mark.parametrize("file_count", FILE_COUNTS)
    def test_parse_files_cached_cold(
        self,
        benchmark: BenchmarkFixture,
        benchmark_dir_factory: Callable[[int], Path],
        file_count: int,
    ) -> None:
        """Measure file parsing time with empty cache (cold start)."""
        base_dir = benchmark_dir_factory(file_count)
        paths = list(base_dir.glob("*.md"))

        def parse_with_empty_cache() -> tuple[list[Any], list[Any]]:
            cache = FileRecordCache()
            return parse_files(paths, base_dir, cache)

        records, warnings = benchmark(parse_with_empty_cache)

        assert len(records) == file_count
        assert len(warnings) == 0

    @pytest.mark.parametrize("file_count", FILE_COUNTS)
    def test_parse_files_cached_warm(
        self,
        benchmark: BenchmarkFixture,
        benchmark_dir_factory: Callable[[int], Path],
        file_count: int,
    ) -> None:
        """Measure file parsing time with warm cache (all hits)."""
        base_dir = benchmark_dir_factory(file_count)
        paths = list(base_dir.glob("*.md"))

        # Warm up cache
        cache = FileRecordCache()
        parse_files(paths, base_dir, cache)

        # Benchmark with warm cache
        records, warnings = benchmark(parse_files, paths, base_dir, cache)

        assert len(records) == file_count
        assert len(warnings) == 0


class TestCreateConnectionBenchmark:
    """Benchmark for create_base_connection function."""

    @pytest.mark.parametrize("file_count", FILE_COUNTS)
    def test_create_connection(
        self,
        benchmark: BenchmarkFixture,
        benchmark_dir_factory: Callable[[int], Path],
        file_count: int,
    ) -> None:
        """Measure DuckDB connection and table creation time."""
        base_dir = benchmark_dir_factory(file_count)
        paths = list(base_dir.glob("*.md"))
        records, _ = parse_files(paths, base_dir, FileRecordCache())

        conn = benchmark(create_base_connection, records)

        result = conn.execute("SELECT COUNT(*) FROM files").fetchone()
        assert result is not None
        assert result[0] == file_count


class TestExecuteQueryBenchmark:
    """Benchmark for execute_query function with different SQL complexity."""

    @pytest.mark.parametrize("file_count", FILE_COUNTS)
    def test_select_all(
        self,
        benchmark: BenchmarkFixture,
        benchmark_dir_factory: Callable[[int], Path],
        file_count: int,
    ) -> None:
        """Measure simple SELECT * query time."""
        base_dir = benchmark_dir_factory(file_count)
        paths = list(base_dir.glob("*.md"))
        records, _ = parse_files(paths, base_dir, FileRecordCache())
        conn = create_base_connection(records)

        result = benchmark(execute_query, conn, "SELECT * FROM files")

        assert result["row_count"] == file_count

    @pytest.mark.parametrize("file_count", FILE_COUNTS)
    def test_where_order_limit(
        self,
        benchmark: BenchmarkFixture,
        benchmark_dir_factory: Callable[[int], Path],
        file_count: int,
    ) -> None:
        """Measure query with WHERE, ORDER BY, and LIMIT."""
        base_dir = benchmark_dir_factory(file_count)
        paths = list(base_dir.glob("*.md"))
        records, _ = parse_files(paths, base_dir, FileRecordCache())
        conn = create_base_connection(records)

        sql = """
            SELECT path, title, date
            FROM files
            WHERE date >= '2024-06-01'
            ORDER BY date DESC
            LIMIT 50
        """
        result = benchmark(execute_query, conn, sql)

        assert result["row_count"] <= 50


class TestQueryE2EBenchmark:
    """End-to-end benchmark for query tool."""

    @pytest.mark.parametrize("file_count", FILE_COUNTS)
    def test_query_e2e(
        self,
        benchmark: BenchmarkFixture,
        benchmark_dir_factory: Callable[[int], Path],
        file_count: int,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Measure full query tool execution time."""
        import frontmatter_mcp.server as server_module
        from frontmatter_mcp.settings import get_settings

        base_dir = benchmark_dir_factory(file_count)

        # Set up server context
        monkeypatch.setenv("FRONTMATTER_BASE_DIR", str(base_dir))
        get_settings.cache_clear()
        server_module._settings = get_settings()
        server_module._semantic_ctx = None

        def run_query() -> dict[str, Any]:
            return server_module.query.fn("*.md", "SELECT * FROM files")

        try:
            result = benchmark(run_query)
            assert result["row_count"] == file_count
        finally:
            server_module._settings = None
            get_settings.cache_clear()
