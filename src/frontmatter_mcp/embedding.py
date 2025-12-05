"""Embedding module for semantic search."""

import numpy as np
from sentence_transformers import SentenceTransformer

# Default embedding model
DEFAULT_MODEL = "cl-nagoya/ruri-v3-30m"


class EmbeddingModel:
    """Lazy-loading wrapper for sentence-transformers model."""

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        """Initialize the embedding model wrapper.

        Args:
            model_name: Name of the sentence-transformers model to use.
        """
        self._model_name = model_name
        self._model: SentenceTransformer | None = None

    @property
    def model_name(self) -> str:
        """Get the model name."""
        return self._model_name

    @property
    def model(self) -> "SentenceTransformer":
        """Get the model, loading it if necessary."""
        if self._model is None:
            self._load_model()
        assert self._model is not None
        return self._model

    def _load_model(self) -> None:
        """Load the sentence-transformers model."""
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError(
                "sentence-transformers is required for semantic search. "
                "Install it with: pip install sentence-transformers"
            ) from e

        self._model = SentenceTransformer(self._model_name)

    @property
    def is_loaded(self) -> bool:
        """Check if the model is loaded."""
        return self._model is not None

    def get_dimension(self) -> int:
        """Get the embedding dimension.

        Returns:
            The dimension of the embedding vectors.
        """
        return self.model.get_sentence_embedding_dimension()

    def encode(self, text: str) -> np.ndarray:
        """Encode text to embedding vector.

        Args:
            text: Text to encode.

        Returns:
            Embedding vector as numpy array.
        """
        return self.model.encode(text)

    def encode_batch(self, texts: list[str]) -> np.ndarray:
        """Encode multiple texts to embedding vectors.

        Args:
            texts: List of texts to encode.

        Returns:
            Embedding vectors as 2D numpy array (n_texts, dimension).
        """
        return self.model.encode(texts)
