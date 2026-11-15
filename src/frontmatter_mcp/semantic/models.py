"""Models for semantic search: the embedding model and the reranker.

Both load lazily (sentence-transformers imports torch, several hundred MB),
and loading is guarded by a lock because the indexing thread and tool calls
can trigger it at the same time.
"""

import threading
from typing import TYPE_CHECKING, Protocol

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder, SentenceTransformer

# ruri-v3 is trained with task prefixes; retrieval uses these two
RURI_V3_QUERY_PREFIX = "検索クエリ: "
RURI_V3_DOCUMENT_PREFIX = "検索文書: "


def default_prefixes(model_name: str) -> tuple[str, str]:
    """Return (query prefix, document prefix) recommended for a model."""
    if "ruri-v3" in model_name:
        return RURI_V3_QUERY_PREFIX, RURI_V3_DOCUMENT_PREFIX
    return "", ""


class EmbeddingModel:
    """Lazy-loading wrapper for sentence-transformers model."""

    def __init__(
        self,
        name: str,
        query_prefix: str | None = None,
        document_prefix: str | None = None,
    ) -> None:
        """Initialize the embedding model wrapper.

        Args:
            name: Name of the sentence-transformers model to use.
            query_prefix: Prefix for search queries. None picks the model's default.
            document_prefix: Prefix for indexed text. None picks the model's default.
        """
        self._name = name
        self._model: "SentenceTransformer | None" = None
        self._lock = threading.Lock()
        default_query, default_document = default_prefixes(name)
        self.query_prefix = default_query if query_prefix is None else query_prefix
        self.document_prefix = (
            default_document if document_prefix is None else document_prefix
        )

    @property
    def name(self) -> str:
        """Get the model name."""
        return self._name

    @property
    def model(self) -> "SentenceTransformer":
        """Get the model, loading it on first use."""
        with self._lock:
            if self._model is None:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self._name)
            return self._model

    @property
    def is_loaded(self) -> bool:
        """Check if the model is loaded."""
        return self._model is not None

    def get_dimension(self) -> int:
        """Get the embedding dimension.

        Returns:
            The dimension of the embedding vectors.
        """
        model = self.model
        # sentence-transformers 6 renamed the method; keep working on 2-5
        getter = getattr(model, "get_embedding_dimension", None)
        if getter is None:
            getter = model.get_sentence_embedding_dimension
        dim = getter()
        if dim is None:
            raise RuntimeError("Model does not report embedding dimension")
        return dim

    def encode_query(self, text: str) -> NDArray[np.float32]:
        """Encode a search query with the query prefix, L2-normalized."""
        vector = self.model.encode(self.query_prefix + text, normalize_embeddings=True)
        return np.asarray(vector, dtype=np.float32)

    def encode_documents(
        self, texts: list[str], batch_size: int = 64
    ) -> NDArray[np.float32]:
        """Encode indexed text with the document prefix, L2-normalized."""
        if not texts:
            return np.zeros((0, self.get_dimension()), dtype=np.float32)
        vectors = self.model.encode(
            [self.document_prefix + t for t in texts],
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype=np.float32)


class Scorer(Protocol):
    """Scores (query, text) pairs; higher means more relevant."""

    def score(self, query: str, texts: list[str]) -> NDArray[np.float32]: ...


class Reranker:
    """Lazy-loading cross-encoder."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._model: "CrossEncoder | None" = None
        self._lock = threading.Lock()

    @property
    def model(self) -> "CrossEncoder":
        with self._lock:
            if self._model is None:
                from sentence_transformers import CrossEncoder

                self._model = CrossEncoder(self.name, max_length=512)
            return self._model

    def score(self, query: str, texts: list[str]) -> NDArray[np.float32]:
        scores = self.model.predict([(query, t) for t in texts], batch_size=16)
        return np.asarray(scores, dtype=np.float32)
