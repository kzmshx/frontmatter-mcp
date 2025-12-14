"""Tests for DuckDB query module."""

from datetime import date
from typing import Any
from unittest.mock import MagicMock

import numpy as np

from frontmatter_mcp.query import create_base_connection, execute_query
from frontmatter_mcp.semantic import add_semantic_columns
from frontmatter_mcp.semantic.context import SemanticContext


def create_mock_semantic_context(
    embeddings: dict[str, np.ndarray[Any, Any]],
    model: MagicMock,
) -> SemanticContext:
    """Create a mock SemanticContext for testing."""
    mock_cache = MagicMock()
    mock_cache.get_all_readonly.return_value = embeddings
    mock_indexer = MagicMock()
    return SemanticContext(model=model, cache=mock_cache, indexer=mock_indexer)


def _execute_query_simple(records: list[dict[str, Any]], sql: str) -> dict[str, Any]:
    """Helper to execute query with new API (no semantic)."""
    conn = create_base_connection(records)
    return execute_query(conn, sql)


class TestExecuteQuery:
    """Tests for execute_query function."""

    def test_select_all(self) -> None:
        """Select all columns from records."""
        records = [
            {"path": "a.md", "title": "Title A"},
            {"path": "b.md", "title": "Title B"},
        ]
        result = _execute_query_simple(records, "SELECT * FROM files")

        assert result["row_count"] == 2
        assert "path" in result["columns"]
        assert "title" in result["columns"]

    def test_select_specific_columns(self) -> None:
        """Select specific columns."""
        records = [
            {"path": "a.md", "title": "Title A", "date": date(2025, 11, 27)},
            {"path": "b.md", "title": "Title B", "date": date(2025, 11, 26)},
        ]
        result = _execute_query_simple(records, "SELECT path, title FROM files")

        assert result["columns"] == ["path", "title"]
        assert len(result["results"]) == 2

    def test_where_clause(self) -> None:
        """Filter records with WHERE clause."""
        records = [
            {"path": "a.md", "date": date(2025, 11, 27)},
            {"path": "b.md", "date": date(2025, 11, 26)},
            {"path": "c.md", "date": date(2025, 11, 25)},
        ]
        result = _execute_query_simple(
            records, "SELECT path FROM files WHERE date >= '2025-11-26'"
        )

        assert result["row_count"] == 2
        paths = [r["path"] for r in result["results"]]
        assert "a.md" in paths
        assert "b.md" in paths
        assert "c.md" not in paths

    def test_order_by(self) -> None:
        """Order results."""
        records = [
            {"path": "b.md", "date": date(2025, 11, 26)},
            {"path": "a.md", "date": date(2025, 11, 27)},
        ]
        result = _execute_query_simple(
            records, "SELECT path FROM files ORDER BY date DESC"
        )

        assert result["results"][0]["path"] == "a.md"
        assert result["results"][1]["path"] == "b.md"

    def test_array_contains(self) -> None:
        """Filter by array containment using from_json."""
        records = [
            {"path": "a.md", "tags": ["mcp", "python"]},
            {"path": "b.md", "tags": ["duckdb"]},
            {"path": "c.md", "tags": ["mcp", "duckdb"]},
        ]
        # Arrays are JSON-encoded strings, use from_json to parse
        result = _execute_query_simple(
            records,
            """SELECT path FROM files
               WHERE list_contains(from_json(tags, '["VARCHAR"]'), 'mcp')""",
        )

        assert result["row_count"] == 2
        paths = [r["path"] for r in result["results"]]
        assert "a.md" in paths
        assert "c.md" in paths

    def test_aggregate_count(self) -> None:
        """Count records."""
        records = [
            {"path": "a.md"},
            {"path": "b.md"},
            {"path": "c.md"},
        ]
        result = _execute_query_simple(records, "SELECT COUNT(*) as count FROM files")

        assert result["row_count"] == 1
        assert result["results"][0]["count"] == 3

    def test_unnest_tags(self) -> None:
        """Unnest array and aggregate using from_json."""
        records = [
            {"path": "a.md", "tags": ["mcp", "python"]},
            {"path": "b.md", "tags": ["mcp"]},
        ]
        # Arrays are JSON-encoded strings, use from_json then unnest
        result = _execute_query_simple(
            records,
            """
            SELECT tag, COUNT(*) AS count
            FROM files, UNNEST(from_json(tags, '["VARCHAR"]')) AS t(tag)
            GROUP BY tag
            ORDER BY count DESC
            """,
        )

        assert result["row_count"] == 2
        assert result["results"][0]["tag"] == "mcp"
        assert result["results"][0]["count"] == 2

    def test_empty_records(self) -> None:
        """Handle empty records list."""
        result = _execute_query_simple([], "SELECT * FROM files")

        assert result["row_count"] == 0
        assert result["results"] == []

    def test_null_handling(self) -> None:
        """Handle NULL values in records."""
        records = [
            {"path": "a.md", "summary": "Has summary"},
            {"path": "b.md", "summary": None},
            {"path": "c.md"},  # No summary key at all
        ]
        result = _execute_query_simple(
            records, "SELECT path FROM files WHERE summary IS NULL"
        )

        paths = [r["path"] for r in result["results"]]
        assert "b.md" in paths
        assert "c.md" in paths
        assert "a.md" not in paths

    def test_templater_expressions_mixed_with_dates(self) -> None:
        """Handle Templater expressions mixed with real dates.

        This tests the scenario where template files contain unexpanded
        Templater expressions like '<% tp.date.now("YYYY-MM-DD") %>'
        alongside real date values from normal files.

        The key assertion is that no type error occurs - all values are
        treated as strings and the query executes successfully.
        """
        records = [
            {"path": "a.md", "date": date(2025, 11, 27)},
            {"path": "b.md", "date": date(2025, 11, 26)},
            # Template file with unexpanded Templater expression
            {"path": "template.md", "date": '<% tp.date.now("YYYY-MM-DD") %>'},
        ]
        # Query should not error - all values are strings now
        # Note: String comparison means '<% ...' sorts after '2025-...'
        result = _execute_query_simple(records, "SELECT path, date FROM files")

        # All 3 records are returned without type errors
        assert result["row_count"] == 3

        # To filter out templates, use LIKE or explicit date patterns
        result_filtered = _execute_query_simple(
            records,
            "SELECT path FROM files WHERE date LIKE '2025-%' AND date >= '2025-11-26'",
        )
        assert result_filtered["row_count"] == 2
        paths = [r["path"] for r in result_filtered["results"]]
        assert "a.md" in paths
        assert "b.md" in paths
        assert "template.md" not in paths

    def test_mixed_type_values_in_same_column(self) -> None:
        """Handle mixed types in the same column.

        All values are serialized to strings, so queries work regardless
        of the original Python type.
        """
        records = [
            {"path": "a.md", "value": "string"},
            {"path": "b.md", "value": 42},
            {"path": "c.md", "value": 3.14},
            {"path": "d.md", "value": True},
            {"path": "e.md", "value": ["a", "b"]},
        ]
        result = _execute_query_simple(records, "SELECT path, value FROM files")

        assert result["row_count"] == 5
        # All values are strings
        values = {r["path"]: r["value"] for r in result["results"]}
        assert values["a.md"] == "string"
        assert values["b.md"] == "42"
        assert values["c.md"] == "3.14"
        assert values["d.md"] == "True"
        assert values["e.md"] == '["a", "b"]'


class TestSemanticSearch:
    """Tests for semantic search integration."""

    def test_query_without_embeddings(self) -> None:
        """Query works without embeddings (backward compatibility)."""
        records = [{"path": "a.md", "title": "A"}]
        result = _execute_query_simple(records, "SELECT * FROM files")
        assert result["row_count"] == 1

    def test_query_with_embedding_column(self) -> None:
        """Query includes embedding column when embeddings provided."""
        records = [{"path": "a.md", "title": "A"}]
        embeddings = {"a.md": np.random.rand(256).astype(np.float32)}

        mock_model = MagicMock()
        mock_model.get_dimension.return_value = 256
        mock_model.encode.return_value = np.random.rand(256).astype(np.float32)

        semantic = create_mock_semantic_context(embeddings, mock_model)

        conn = create_base_connection(records)
        add_semantic_columns(conn, semantic)
        result = execute_query(conn, "SELECT path, embedding FROM files")

        assert result["row_count"] == 1
        assert "embedding" in result["columns"]
        assert result["results"][0]["embedding"] is not None

    def test_embed_function_registered(self) -> None:
        """embed() function can be used in SQL."""
        records = [{"path": "a.md", "title": "A"}]
        embeddings = {"a.md": np.random.rand(256).astype(np.float32)}

        mock_model = MagicMock()
        mock_model.get_dimension.return_value = 256
        mock_model.encode.return_value = np.random.rand(256).astype(np.float32)

        semantic = create_mock_semantic_context(embeddings, mock_model)

        conn = create_base_connection(records)
        add_semantic_columns(conn, semantic)
        result = execute_query(
            conn, "SELECT path, embed('test query') as query_vec FROM files"
        )

        assert result["row_count"] == 1
        assert "query_vec" in result["columns"]
        mock_model.encode.assert_called_with("test query")

    def test_cosine_similarity_calculation(self) -> None:
        """array_cosine_similarity works with embeddings."""
        # Create embeddings where a.md is more similar to query than b.md
        query_vec = np.array([1.0, 0.0, 0.0] + [0.0] * 253, dtype=np.float32)
        vec_a = np.array([0.9, 0.1, 0.0] + [0.0] * 253, dtype=np.float32)  # Similar
        vec_b = np.array([0.0, 1.0, 0.0] + [0.0] * 253, dtype=np.float32)  # Different

        records = [
            {"path": "a.md", "title": "A"},
            {"path": "b.md", "title": "B"},
        ]
        embeddings = {"a.md": vec_a, "b.md": vec_b}

        mock_model = MagicMock()
        mock_model.get_dimension.return_value = 256
        mock_model.encode.return_value = query_vec

        semantic = create_mock_semantic_context(embeddings, mock_model)

        conn = create_base_connection(records)
        add_semantic_columns(conn, semantic)
        result = execute_query(
            conn,
            """
            SELECT path, array_cosine_similarity(embedding, embed('query')) as score
            FROM files
            ORDER BY score DESC
            """,
        )

        assert result["row_count"] == 2
        # a.md should have higher score (more similar)
        assert result["results"][0]["path"] == "a.md"
        assert result["results"][0]["score"] > result["results"][1]["score"]

    def test_embedding_null_for_missing_path(self) -> None:
        """Embedding is NULL for paths not in embeddings dict."""
        records = [
            {"path": "a.md", "title": "A"},
            {"path": "b.md", "title": "B"},  # No embedding for this
        ]
        embeddings = {"a.md": np.random.rand(256).astype(np.float32)}

        mock_model = MagicMock()
        mock_model.get_dimension.return_value = 256

        semantic = create_mock_semantic_context(embeddings, mock_model)

        conn = create_base_connection(records)
        add_semantic_columns(conn, semantic)
        result = execute_query(conn, "SELECT path, embedding FROM files ORDER BY path")

        assert result["row_count"] == 2
        assert result["results"][0]["path"] == "a.md"
        assert result["results"][0]["embedding"] is not None
        assert result["results"][1]["path"] == "b.md"
        assert result["results"][1]["embedding"] is None
