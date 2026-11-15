"""Benchmarks for the hybrid search index (synthetic chunks)."""

import numpy as np
import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from frontmatter_mcp.semantic.chunking import chunk_markdown
from frontmatter_mcp.semantic.search import Bm25Index, SearchIndex
from frontmatter_mcp.semantic.store import ChunkRows

WORDS = [
    "ダーツ",
    "読書",
    "散歩",
    "珈琲",
    "仕事",
    "障害",
    "旅行",
    "京都",
    "雨",
    "誕生日",
]


def _rows(n_docs: int, chunks_per_doc: int = 10, dim: int = 256) -> ChunkRows:
    rng = np.random.default_rng(0)
    n = n_docs * chunks_per_doc
    texts = ["".join(rng.choice(WORDS, size=40)) for _ in range(n)]
    vectors = rng.random((n, dim)).astype(np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    return ChunkRows(
        paths=[f"d{i // chunks_per_doc:05d}.md" for i in range(n)],
        lines=np.arange(n, dtype=np.int64),
        headings=[""] * n,
        texts=texts,
        vectors=vectors,
    )


@pytest.mark.parametrize("n_docs", [500, 2000])
def test_bm25_build(benchmark: BenchmarkFixture, n_docs: int) -> None:
    rows = _rows(n_docs)
    benchmark(Bm25Index, rows.texts)


@pytest.mark.parametrize("n_docs", [500, 2000])
def test_search_without_reranker(benchmark: BenchmarkFixture, n_docs: int) -> None:
    index = SearchIndex(_rows(n_docs))
    _ = index.bm25  # build once, outside the measurement
    query = np.ones(256, dtype=np.float32) / 16
    allowed = {f"d{i:05d}.md" for i in range(0, n_docs, 2)}
    hits = benchmark(index.search, query, "ダーツ 京都", 10, allowed)
    assert len(hits) == 10


def test_chunk_markdown(benchmark: BenchmarkFixture) -> None:
    text = "---\ntitle: x\n---\n" + "\n".join(
        f"## H{i}\n" + "本文の段落。" * 30 for i in range(50)
    )
    chunks = benchmark(chunk_markdown, text)
    assert chunks
