"""Shared fixtures: a small vault, the application state, and fake models."""

import hashlib
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray

from frontmatter_mcp.dependencies import AppState, reset_state, set_state
from frontmatter_mcp.semantic import ChunkIndexer, ChunkStore, SemanticContext
from frontmatter_mcp.semantic.indexer import IndexerState
from frontmatter_mcp.semantic.store import ChunkRows
from frontmatter_mcp.settings import Settings

DIM = 64


class FakeEmbeddingModel:
    """Deterministic stand-in for EmbeddingModel.

    Embeds text as hashed character bigrams, so texts that share wording are
    similar. Same interface as EmbeddingModel, without loading anything.
    """

    name = "fake-model"
    query_prefix = ""
    document_prefix = ""

    def __init__(
        self, dim: int = DIM, query_vector: NDArray[np.float32] | None = None
    ) -> None:
        self.dim = dim
        self.query_vector = query_vector
        self.queries: list[str] = []
        self.encoded_documents: list[str] = []
        self.fail_with: Exception | None = None

    @property
    def is_loaded(self) -> bool:
        return True

    def get_dimension(self) -> int:
        return self.dim

    def _vector(self, text: str) -> NDArray[np.float32]:
        v = np.zeros(self.dim, dtype=np.float32)
        for a, b in zip(text, text[1:], strict=False):
            h = hashlib.md5((a + b).encode()).digest()
            v[int.from_bytes(h[:4], "little") % self.dim] += 1.0
        norm = np.linalg.norm(v)
        return v / norm if norm else v

    def encode_query(self, text: str) -> NDArray[np.float32]:
        """The vector given to the constructor, or the text's own vector."""
        self.queries.append(text)
        if self.query_vector is not None:
            return self.query_vector
        return self._vector(text)

    def encode_documents(
        self, texts: list[str], batch_size: int = 64
    ) -> NDArray[np.float32]:
        if self.fail_with is not None:
            raise self.fail_with
        self.encoded_documents.extend(texts)
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.stack([self._vector(t) for t in texts])


class StaticChunkStore:
    """Store stand-in that serves fixed chunk rows; nothing is on disk."""

    def __init__(self, rows: ChunkRows) -> None:
        self.rows = rows
        self.path = Path("/nonexistent") / "embeddings.duckdb"

    def load_chunks(self) -> ChunkRows:
        return self.rows


def chunk_rows(vectors: dict[str, NDArray[np.float32]], dim: int = DIM) -> ChunkRows:
    """Chunk rows with one chunk per document."""
    paths = sorted(vectors)
    return ChunkRows(
        paths=paths,
        lines=np.ones(len(paths), dtype=np.int64),
        headings=[""] * len(paths),
        texts=[""] * len(paths),
        vectors=(
            np.array([vectors[p] for p in paths], dtype=np.float32)
            if paths
            else np.zeros((0, dim), dtype=np.float32)
        ),
    )


def static_semantic_context(
    vectors: dict[str, NDArray[np.float32]], model: FakeEmbeddingModel
) -> SemanticContext:
    """A semantic context over fixed document vectors, as after one run."""
    store: Any = StaticChunkStore(chunk_rows(vectors, model.dim))
    indexer: Any = SimpleNamespace(generation=1, state=IndexerState.READY)
    fake_model: Any = model
    return SemanticContext(model=fake_model, store=store, indexer=indexer)


class FakeReranker:
    """Scores a text by how many characters of the query it contains."""

    def score(self, query: str, texts: list[str]) -> NDArray[np.float32]:
        return np.array([sum(ch in t for ch in query) for t in texts], np.float32)


def write_md(base: Path, name: str, frontmatter: str, body: str = "") -> Path:
    """Write a Markdown file with the given frontmatter block and body."""
    path = base / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}---\n{body}")
    return path


@pytest.fixture
def base_dir(tmp_path: Path) -> Path:
    """A small vault: a.md, b.md and subdir/c.md."""
    base = tmp_path / "vault"
    base.mkdir()
    write_md(base, "a.md", "date: 2025-11-27\ntags: [python, mcp]\n", "# File A\n")
    write_md(base, "b.md", "date: 2025-11-26\ntags: [duckdb]\n", "# File B\n")
    write_md(
        base,
        "subdir/c.md",
        "date: 2025-11-25\ntags: [python]\nsummary: A summary\n",
        "# File C\n",
    )
    return base


@pytest.fixture
def state(base_dir: Path) -> Iterator[AppState]:
    """Application state for base_dir with semantic search off."""
    app_state = AppState(settings=Settings(base_dir=base_dir))
    set_state(app_state)
    yield app_state
    reset_state()


@pytest.fixture
def semantic_ctx(base_dir: Path, tmp_path: Path) -> Iterator[SemanticContext]:
    """Application state with semantic search on, using the fake model."""
    settings = Settings(
        base_dir=base_dir, enable_semantic=True, cache_dir=tmp_path / "cache"
    )
    model: Any = FakeEmbeddingModel()
    store = ChunkStore(settings.cache_dir, model)
    from frontmatter_mcp.paths import list_markdown_files

    indexer = ChunkIndexer(
        store, model, lambda: list_markdown_files(base_dir), base_dir
    )
    ctx = SemanticContext(model=model, store=store, indexer=indexer, reranker=None)
    app_state = AppState(settings=settings)
    app_state._semantic = ctx
    set_state(app_state)
    yield ctx
    indexer.wait(timeout=10)
    store.close()
    reset_state()


def tool_deps(state: AppState) -> dict[str, Any]:
    """Keyword arguments that FastMCP's Depends would inject."""
    return {
        "settings": state.settings,
        "cache": state.file_cache,
        "semantic_ctx": state.semantic,
    }
