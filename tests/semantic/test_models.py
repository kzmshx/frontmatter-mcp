"""Tests for the embedding model and reranker wrappers."""

from typing import Any

import numpy as np
import pytest

from frontmatter_mcp.semantic.models import (
    RURI_V3_DOCUMENT_PREFIX,
    RURI_V3_QUERY_PREFIX,
    EmbeddingModel,
    default_prefixes,
)
from frontmatter_mcp.settings import DEFAULT_EMBEDDING_MODEL


class _FakeSentenceTransformer:
    """Records what it was asked to encode."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    def encode(self, inputs: Any, **kwargs: Any) -> np.ndarray:
        self.calls.append((inputs, kwargs))
        n = 1 if isinstance(inputs, str) else len(inputs)
        out = np.ones((n, 4), dtype=np.float32)
        return out[0] if isinstance(inputs, str) else out

    def get_embedding_dimension(self) -> int:
        return 4


def _with_fake(model: EmbeddingModel) -> _FakeSentenceTransformer:
    fake = _FakeSentenceTransformer()
    model._model = fake  # type: ignore[assignment]
    return fake


class TestEmbeddingModel:
    def test_lazy_loading(self) -> None:
        assert not EmbeddingModel(DEFAULT_EMBEDDING_MODEL).is_loaded

    def test_ruri_v3_prefixes_by_default(self) -> None:
        assert default_prefixes("cl-nagoya/ruri-v3-30m") == (
            RURI_V3_QUERY_PREFIX,
            RURI_V3_DOCUMENT_PREFIX,
        )
        assert default_prefixes("intfloat/multilingual-e5-small") == ("", "")

    def test_prefixes_can_be_overridden(self) -> None:
        model = EmbeddingModel(
            "cl-nagoya/ruri-v3-30m", query_prefix="", document_prefix="d: "
        )
        assert (model.query_prefix, model.document_prefix) == ("", "d: ")

    def test_encode_query_adds_prefix_and_normalizes(self) -> None:
        model = EmbeddingModel("cl-nagoya/ruri-v3-30m")
        fake = _with_fake(model)
        vector = model.encode_query("誕生日")
        inputs, kwargs = fake.calls[0]
        assert inputs == RURI_V3_QUERY_PREFIX + "誕生日"
        assert kwargs["normalize_embeddings"] is True
        assert vector.dtype == np.float32

    def test_encode_documents_adds_prefix(self) -> None:
        model = EmbeddingModel("cl-nagoya/ruri-v3-30m")
        fake = _with_fake(model)
        vectors = model.encode_documents(["a", "b"])
        inputs, kwargs = fake.calls[0]
        assert inputs == [RURI_V3_DOCUMENT_PREFIX + "a", RURI_V3_DOCUMENT_PREFIX + "b"]
        assert kwargs["normalize_embeddings"] is True
        assert vectors.shape == (2, 4)

    def test_encode_documents_empty(self) -> None:
        model = EmbeddingModel("cl-nagoya/ruri-v3-30m")
        _with_fake(model)
        assert model.encode_documents([]).shape == (0, 4)


@pytest.fixture(scope="module")
def real_model() -> EmbeddingModel:
    """The real default model, loaded once for the module."""
    return EmbeddingModel(DEFAULT_EMBEDDING_MODEL)


@pytest.mark.slow
class TestEmbeddingModelWithRealModel:
    """Tests that load the real model (run with: pytest -m slow)."""

    def test_dimension(self, real_model: EmbeddingModel) -> None:
        assert real_model.get_dimension() == 256

    def test_query_and_documents_are_unit_vectors(
        self, real_model: EmbeddingModel
    ) -> None:
        q = real_model.encode_query("テスト文章")
        d = real_model.encode_documents(["テスト文章"])
        assert np.isclose(np.linalg.norm(q), 1.0, atol=1e-4)
        assert np.isclose(np.linalg.norm(d[0]), 1.0, atol=1e-4)

    def test_similar_texts_rank_higher(self, real_model: EmbeddingModel) -> None:
        q = real_model.encode_query("今日は体調が良い")
        docs = real_model.encode_documents(
            ["今日は調子が良い", "プログラミングの勉強をした"]
        )
        scores = docs @ q
        assert scores[0] > scores[1]
