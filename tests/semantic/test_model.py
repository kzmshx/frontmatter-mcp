"""Tests for semantic model module."""

import pytest

from frontmatter_mcp.semantic.model import EmbeddingModel
from frontmatter_mcp.settings import DEFAULT_EMBEDDING_MODEL


class TestEmbeddingModel:
    """Tests for EmbeddingModel class."""

    def test_model_name_is_preserved(self) -> None:
        """Model name is preserved."""
        model = EmbeddingModel("custom-model")
        assert model.name == "custom-model"

    def test_lazy_loading(self) -> None:
        """Model is not loaded until accessed."""
        model = EmbeddingModel(DEFAULT_EMBEDDING_MODEL)
        assert not model.is_loaded


@pytest.mark.slow
class TestEmbeddingModelWithRealModel:
    """Tests that require loading the actual model.

    These tests are marked as slow and require sentence-transformers to be installed.
    Run with: pytest -m slow
    """

    def test_model_loads(self) -> None:
        """Model loads successfully."""
        model = EmbeddingModel(DEFAULT_EMBEDDING_MODEL)
        assert model.is_loaded is False
        _ = model.model  # Trigger loading
        assert model.is_loaded is True

    def test_get_dimension(self) -> None:
        """Get embedding dimension from model."""
        model = EmbeddingModel(DEFAULT_EMBEDDING_MODEL)
        dim = model.get_dimension()
        assert isinstance(dim, int)
        assert dim > 0
        # ruri-v3-30m has 256 dimensions
        assert dim == 256

    def test_encode(self) -> None:
        """Encode text to vector."""
        model = EmbeddingModel(DEFAULT_EMBEDDING_MODEL)
        dim = model.get_dimension()
        embedding = model.encode("テスト文章")

        assert embedding.shape == (dim,)
        assert embedding.dtype.kind == "f"  # float type

    def test_similar_texts_have_similar_embeddings(self) -> None:
        """Similar texts produce similar embeddings."""
        model = EmbeddingModel(DEFAULT_EMBEDDING_MODEL)

        # Similar texts
        text1 = "今日は体調が良い"
        text2 = "今日は調子が良い"
        # Different text
        text3 = "プログラミングの勉強をした"

        emb1 = model.encode(text1)
        emb2 = model.encode(text2)
        emb3 = model.encode(text3)

        # Cosine similarity
        def cosine_sim(a, b):
            return (a @ b) / (sum(a**2) ** 0.5 * sum(b**2) ** 0.5)

        sim_12 = cosine_sim(emb1, emb2)
        sim_13 = cosine_sim(emb1, emb3)

        # Similar texts should have higher similarity
        assert sim_12 > sim_13
