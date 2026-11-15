"""Tests for the semantic SQL columns: embedding and embed()."""

from typing import Any
from unittest.mock import MagicMock

import numpy as np

from frontmatter_mcp.semantic import add_semantic_columns
from frontmatter_mcp.semantic.context import SemanticContext
from frontmatter_mcp.sql import create_files_connection, execute_query


def _rows(embeddings: dict[str, Any]) -> Any:
    """Chunk rows with one chunk per document."""
    from frontmatter_mcp.semantic.store import ChunkRows

    paths = sorted(embeddings)
    dim = len(next(iter(embeddings.values()))) if embeddings else 256
    return ChunkRows(
        paths=paths,
        lines=np.ones(len(paths), dtype=np.int64),
        headings=[""] * len(paths),
        texts=[""] * len(paths),
        vectors=(
            np.array([embeddings[p] for p in paths], dtype=np.float32)
            if paths
            else np.zeros((0, dim), dtype=np.float32)
        ),
    )


def create_mock_semantic_context(
    embeddings: dict[str, np.ndarray[Any, Any]],
    model: MagicMock,
) -> SemanticContext:
    """Create a mock SemanticContext for testing."""
    mock_store = MagicMock()
    mock_store.load_chunks.return_value = _rows(embeddings)
    mock_indexer = MagicMock()
    return SemanticContext(model=model, store=mock_store, indexer=mock_indexer)


def _execute_query_simple(records: list[dict[str, Any]], sql: str) -> dict[str, Any]:
    """Helper to execute query with new API (no semantic)."""
    conn = create_files_connection(records)
    return execute_query(conn, sql)


class TestSemanticNullEmbedding:
    """Files without an index entry."""

    def test_unindexed_files_get_null_embedding(self) -> None:
        """Files without chunks are NULL, not an error (outer-join regression)."""
        records = [{"path": "a.md"}, {"path": "b.md"}]
        model = MagicMock()
        model.get_dimension.return_value = 256
        semantic = create_mock_semantic_context(
            {"a.md": np.random.rand(256).astype(np.float32)}, model
        )
        conn = create_files_connection(records)
        add_semantic_columns(conn, semantic)
        result = execute_query(
            conn, "SELECT path, embedding IS NULL AS missing FROM files ORDER BY path"
        )
        assert [r["missing"] for r in result["results"]] == [False, True]


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
        mock_model.encode_query.return_value = np.random.rand(256).astype(np.float32)

        semantic = create_mock_semantic_context(embeddings, mock_model)

        conn = create_files_connection(records)
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
        mock_model.encode_query.return_value = np.random.rand(256).astype(np.float32)

        semantic = create_mock_semantic_context(embeddings, mock_model)

        conn = create_files_connection(records)
        add_semantic_columns(conn, semantic)
        result = execute_query(
            conn, "SELECT path, embed('test query') as query_vec FROM files"
        )

        assert result["row_count"] == 1
        assert "query_vec" in result["columns"]
        mock_model.encode_query.assert_called_with("test query")

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
        mock_model.encode_query.return_value = query_vec

        semantic = create_mock_semantic_context(embeddings, mock_model)

        conn = create_files_connection(records)
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

        conn = create_files_connection(records)
        add_semantic_columns(conn, semantic)
        result = execute_query(conn, "SELECT path, embedding FROM files ORDER BY path")

        assert result["row_count"] == 2
        assert result["results"][0]["path"] == "a.md"
        assert result["results"][0]["embedding"] is not None
        assert result["results"][1]["path"] == "b.md"
        assert result["results"][1]["embedding"] is None
