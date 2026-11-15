"""Hybrid search over document chunks.

Pipeline for one query:

1. Dense: cosine similarity between the query and every chunk vector
   (ruri-v3 with its query/document prefixes). A document scores as its best chunk.
2. Lexical: BM25 over character bigrams. Bigrams need no Japanese tokenizer and
   catch exact names and phrases that embeddings blur.
3. Candidates: the top documents from each list, merged.
4. Rerank: a cross-encoder scores (query, chunk) for the best chunks of each
   candidate. Without a reranker, the two lists are fused with weighted
   reciprocal rank fusion instead.

Measured on a 1,900-file Japanese Obsidian vault (27,680 chunks) with 16 queries
that each have one known target document: the target ranked first for 2 queries
with the previous whole-document embeddings, 12 with dense + BM25 fusion, and 13
with reranking (top 5: 6, 14, 15). Reranking adds about 0.3 s per query.
"""

import threading
import unicodedata
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy import sparse
from sklearn.feature_extraction.text import CountVectorizer

from frontmatter_mcp.semantic.cache import ChunkRows

# Documents taken from each of the dense and lexical lists before reranking
CANDIDATES_PER_LIST = 20
# Chunks per candidate document sent to the reranker
CHUNKS_PER_CANDIDATE = 2
# Weighted RRF used when no reranker is configured
RRF_K = 60
RRF_WEIGHTS = (1.0, 0.5)  # dense, lexical
# BM25 parameters
BM25_K1 = 1.2
BM25_B = 0.75
# Longest chunk text returned to the caller
MAX_RESULT_CHARS = 800


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).lower()


class Bm25Index:
    """BM25 over character bigrams of each chunk."""

    def __init__(self, texts: list[str]) -> None:
        self._vectorizer = CountVectorizer(
            analyzer="char", ngram_range=(2, 2), preprocessor=_normalize
        )
        if texts:
            tf = self._vectorizer.fit_transform(texts).astype(np.float32)
        else:
            tf = sparse.csr_matrix((0, 0), dtype=np.float32)
        self._tf = sparse.csc_matrix(tf)
        n = self._tf.shape[0]
        lengths = np.asarray(self._tf.sum(axis=1)).ravel()
        self._len_norm = (
            BM25_K1 * (1 - BM25_B + BM25_B * lengths / lengths.mean())
            if n
            else np.zeros(0, dtype=np.float32)
        )
        df = np.diff(self._tf.indptr)
        self._idf = np.log(1 + (n - df + 0.5) / (df + 0.5)).astype(np.float32)
        self._n = n

    def scores(self, query: str) -> NDArray[np.float32]:
        """BM25 score of every chunk for the query."""
        result = np.zeros(self._n, dtype=np.float32)
        if not self._n:
            return result
        for j in set(self._vectorizer.transform([query]).indices):
            start, end = self._tf.indptr[j], self._tf.indptr[j + 1]
            rows = self._tf.indices[start:end]
            f = self._tf.data[start:end]
            weight = f * (BM25_K1 + 1) / (f + self._len_norm[rows])
            result[rows] += self._idf[j] * weight
        return result


@dataclass
class SearchHit:
    """One result: a document and its best-matching chunk."""

    path: str
    line: int
    heading: str
    text: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        text = self.text
        if len(text) > MAX_RESULT_CHARS:
            text = text[:MAX_RESULT_CHARS] + "…"
        return {
            "path": self.path,
            "line": self.line,
            "heading": self.heading,
            "text": text,
            "score": round(self.score, 4),
        }


class Reranker:
    """Lazy-loading cross-encoder."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._model: Any = None
        self._lock = threading.Lock()

    def score(self, query: str, texts: list[str]) -> NDArray[np.float32]:
        with self._lock:
            if self._model is None:
                from sentence_transformers import CrossEncoder

                self._model = CrossEncoder(self.name, max_length=512)
        scores = self._model.predict([(query, t) for t in texts], batch_size=16)
        return np.asarray(scores, dtype=np.float32)


class SearchIndex:
    """In-memory chunks, their vectors, and the BM25 index."""

    def __init__(self, rows: ChunkRows) -> None:
        self.rows = rows
        self._paths = np.array(rows.paths, dtype=object)
        self._bm25: Bm25Index | None = None
        self._lock = threading.Lock()

    @property
    def bm25(self) -> Bm25Index:
        with self._lock:
            if self._bm25 is None:
                self._bm25 = Bm25Index(self.rows.texts)
            return self._bm25

    def _rank_documents(
        self, scores: NDArray[np.float32], mask: NDArray[np.bool_], limit: int
    ) -> list[tuple[str, int]]:
        """Documents ordered by their best chunk: [(path, chunk index)]."""
        order = np.argsort(-np.where(mask, scores, -np.inf), kind="stable")
        out: list[tuple[str, int]] = []
        seen: set[str] = set()
        for i in order:
            if not mask[i]:
                break
            path = self.rows.paths[i]
            if path in seen:
                continue
            seen.add(path)
            out.append((path, int(i)))
            if len(out) == limit:
                break
        return out

    def search(
        self,
        query_vector: NDArray[np.float32],
        query: str,
        limit: int,
        allowed_paths: set[str] | None = None,
        reranker: Reranker | None = None,
    ) -> list[SearchHit]:
        """Run the hybrid pipeline described in the module docstring."""
        if not len(self.rows):
            return []
        if allowed_paths is None:
            mask = np.ones(len(self.rows), dtype=bool)
        else:
            mask = np.isin(self._paths, list(allowed_paths))
        if not mask.any():
            return []

        dense_scores = self.rows.vectors @ query_vector
        lexical_scores = self.bm25.scores(query)
        pool = max(CANDIDATES_PER_LIST, limit)
        dense = self._rank_documents(dense_scores, mask, pool)
        has_word = mask & (lexical_scores > 0)
        lexical = self._rank_documents(lexical_scores, has_word, pool)

        if reranker is None:
            return self._fuse(dense, lexical, dense_scores, limit)

        candidates = list(dict.fromkeys(p for p, _ in dense + lexical))
        pairs: list[tuple[str, int]] = []
        for path in candidates:
            idx = np.flatnonzero(self._paths == path)
            best = idx[np.argsort(-dense_scores[idx])[:CHUNKS_PER_CANDIDATE]]
            lexical_best = int(idx[np.argmax(lexical_scores[idx])])
            chosen = list(dict.fromkeys([*map(int, best), lexical_best]))
            pairs.extend((path, i) for i in chosen)
        scores = reranker.score(query, [self.rows.texts[i] for _, i in pairs])
        best_by_path: dict[str, tuple[float, int]] = {}
        for (path, i), score in zip(pairs, scores, strict=True):
            if path not in best_by_path or score > best_by_path[path][0]:
                best_by_path[path] = (float(score), i)
        ranked = sorted(best_by_path.items(), key=lambda kv: -kv[1][0])[:limit]
        return [self._hit(path, i, score) for path, (score, i) in ranked]

    def _fuse(
        self,
        dense: list[tuple[str, int]],
        lexical: list[tuple[str, int]],
        dense_scores: NDArray[np.float32],
        limit: int,
    ) -> list[SearchHit]:
        fused: dict[str, tuple[float, int]] = {}
        for weight, ranking in zip(RRF_WEIGHTS, (dense, lexical), strict=True):
            for rank, (path, i) in enumerate(ranking):
                score, chunk = fused.get(path, (0.0, i))
                if dense_scores[i] > dense_scores[chunk]:
                    chunk = i
                fused[path] = (score + weight / (RRF_K + rank + 1), chunk)
        ranked = sorted(fused.items(), key=lambda kv: -kv[1][0])[:limit]
        return [self._hit(path, i, score) for path, (score, i) in ranked]

    def _hit(self, path: str, i: int, score: float) -> SearchHit:
        return SearchHit(
            path=path,
            line=int(self.rows.lines[i]),
            heading=self.rows.headings[i],
            text=self.rows.texts[i],
            score=score,
        )
