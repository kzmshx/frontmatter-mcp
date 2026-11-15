"""Tests for the semantic SQL columns: embedding and embed()."""

import numpy as np

from frontmatter_mcp.semantic import add_semantic_columns
from frontmatter_mcp.sql import create_files_connection, execute_query
from tests.conftest import FakeEmbeddingModel, static_semantic_context

DIM = 256


def _random_vector() -> np.ndarray:
    return np.random.rand(DIM).astype(np.float32)


class TestSemanticNullEmbedding:
    """Files without an index entry."""

    def test_unindexed_files_get_null_embedding(self) -> None:
        """Files without chunks are NULL, not an error (outer-join regression)."""
        records = [{"path": "a.md"}, {"path": "b.md"}]
        semantic = static_semantic_context(
            {"a.md": _random_vector()}, FakeEmbeddingModel(DIM)
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
        conn = create_files_connection([{"path": "a.md", "title": "A"}])
        result = execute_query(conn, "SELECT * FROM files")
        assert result["row_count"] == 1

    def test_query_with_embedding_column(self) -> None:
        """Query includes embedding column when embeddings provided."""
        semantic = static_semantic_context(
            {"a.md": _random_vector()}, FakeEmbeddingModel(DIM)
        )
        conn = create_files_connection([{"path": "a.md", "title": "A"}])
        add_semantic_columns(conn, semantic)
        result = execute_query(conn, "SELECT path, embedding FROM files")

        assert result["row_count"] == 1
        assert "embedding" in result["columns"]
        assert result["results"][0]["embedding"] is not None

    def test_embed_function_registered(self) -> None:
        """embed() function can be used in SQL."""
        model = FakeEmbeddingModel(DIM)
        semantic = static_semantic_context({"a.md": _random_vector()}, model)
        conn = create_files_connection([{"path": "a.md", "title": "A"}])
        add_semantic_columns(conn, semantic)
        result = execute_query(
            conn, "SELECT path, embed('test query') as query_vec FROM files"
        )

        assert result["row_count"] == 1
        assert "query_vec" in result["columns"]
        assert model.queries == ["test query"]

    def test_cosine_similarity_calculation(self) -> None:
        """array_cosine_similarity works with embeddings."""
        query_vec = np.array([1.0, 0.0, 0.0] + [0.0] * 253, dtype=np.float32)
        vec_a = np.array([0.9, 0.1, 0.0] + [0.0] * 253, dtype=np.float32)  # Similar
        vec_b = np.array([0.0, 1.0, 0.0] + [0.0] * 253, dtype=np.float32)  # Different
        semantic = static_semantic_context(
            {"a.md": vec_a, "b.md": vec_b},
            FakeEmbeddingModel(DIM, query_vector=query_vec),
        )
        conn = create_files_connection(
            [{"path": "a.md", "title": "A"}, {"path": "b.md", "title": "B"}]
        )
        add_semantic_columns(conn, semantic)
        result = execute_query(
            conn,
            "SELECT path, array_cosine_similarity(embedding, embed('query')) as score "
            "FROM files ORDER BY score DESC",
        )

        assert result["row_count"] == 2
        assert result["results"][0]["path"] == "a.md"
        assert result["results"][0]["score"] > result["results"][1]["score"]

    def test_embedding_null_for_missing_path(self) -> None:
        """Embedding is NULL for paths not in embeddings dict."""
        semantic = static_semantic_context(
            {"a.md": _random_vector()}, FakeEmbeddingModel(DIM)
        )
        conn = create_files_connection(
            [{"path": "a.md", "title": "A"}, {"path": "b.md", "title": "B"}]
        )
        add_semantic_columns(conn, semantic)
        result = execute_query(conn, "SELECT path, embedding FROM files ORDER BY path")

        assert result["row_count"] == 2
        assert result["results"][0]["embedding"] is not None
        assert result["results"][1]["path"] == "b.md"
        assert result["results"][1]["embedding"] is None
