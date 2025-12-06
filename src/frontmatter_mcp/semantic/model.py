"""Embedding model module for semantic search."""

from typing import Any, cast

import numpy as np
from numpy.typing import NDArray
from sentence_transformers import SentenceTransformer


class EmbeddingModel:
    """Lazy-loading wrapper for sentence-transformers model."""

    def __init__(self, name: str) -> None:
        """Initialize the embedding model wrapper.

        Args:
            model_name: Name of the sentence-transformers model to use.
        """
        self._name = name
        self._model: SentenceTransformer | None = None

    @property
    def name(self) -> str:
        """Get the model name."""
        return self._name

    @property
    def model(self) -> SentenceTransformer:
        """Get the model, loading it if necessary."""
        if self._model is None:
            self._load_model()
        assert self._model is not None
        return self._model

    def _load_model(self) -> None:
        """Load the sentence-transformers model."""
        self._model = SentenceTransformer(self._name)

    @property
    def is_loaded(self) -> bool:
        """Check if the model is loaded."""
        return self._model is not None

    def get_dimension(self) -> int:
        """Get the embedding dimension.

        Returns:
            The dimension of the embedding vectors.
        """
        dim = self.model.get_sentence_embedding_dimension()
        if dim is None:
            raise RuntimeError("Model does not report embedding dimension")
        return dim

    def encode(self, text: str) -> NDArray[np.floating[Any]]:
        """Encode text to embedding vector.

        Args:
            text: Text to encode.

        Returns:
            Embedding vector as numpy array.
        """
        return cast(NDArray[np.floating[Any]], self.model.encode(text))
