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

See ADR 0012 for the measurements behind this design.
"""

import threading
import unicodedata
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from frontmatter_mcp.semantic.models import Scorer
from frontmatter_mcp.semantic.store import ChunkRows

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
# Bigrams are hashed into this many columns. Hashing avoids keeping a
# vocabulary dict of every bigram in memory; collisions at this size are rare
BIGRAM_FEATURES = 2**20
# Longest chunk text returned to the caller
MAX_RESULT_CHARS = 800


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).lower()


class Bm25Index:
    """BM25 over character bigrams of each chunk."""

    def __init__(self, texts: list[str]) -> None:
        # Imported lazily so the server starts without scipy / scikit-learn
        from scipy import sparse
        from sklearn.feature_extraction.text import HashingVectorizer

        self._vectorizer = HashingVectorizer(
            analyzer="char",
            ngram_range=(2, 2),
            preprocessor=_normalize,
            n_features=BIGRAM_FEATURES,
            alternate_sign=False,
            norm=None,
            dtype=np.float32,
        )
        if texts:
            tf = self._vectorizer.transform(texts)
        else:
            tf = sparse.csr_matrix((0, BIGRAM_FEATURES), dtype=np.float32)
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


class SearchIndex:
    """In-memory chunks, their vectors, and the BM25 index.

    Chunks are grouped by document: chunk rows of one path are contiguous, so
    document-level operations (best chunk per document, path filters, mean
    vectors) work on index ranges instead of comparing path strings.
    """

    def __init__(self, rows: ChunkRows) -> None:
        if any(a > b for a, b in zip(rows.paths, rows.paths[1:], strict=False)):
            order = sorted(range(len(rows)), key=rows.paths.__getitem__)
            rows = ChunkRows(
                paths=[rows.paths[i] for i in order],
                lines=rows.lines[order],
                headings=[rows.headings[i] for i in order],
                texts=[rows.texts[i] for i in order],
                vectors=rows.vectors[order],
            )
        self.rows = rows
        paths = rows.paths
        starts = [i for i in range(len(paths)) if i == 0 or paths[i] != paths[i - 1]]
        self._doc_paths = [rows.paths[i] for i in starts]
        self._doc_starts = np.array(starts, dtype=np.int64)
        self._doc_ends = np.append(self._doc_starts[1:], len(rows)).astype(np.int64)
        self._doc_of_chunk = np.repeat(
            np.arange(len(starts)), self._doc_ends - self._doc_starts
        )
        self._bm25: Bm25Index | None = None
        self._doc_vectors: dict[str, NDArray[np.float32]] | None = None
        self._lock = threading.Lock()

    @property
    def bm25(self) -> Bm25Index:
        with self._lock:
            if self._bm25 is None:
                self._bm25 = Bm25Index(self.rows.texts)
            return self._bm25

    def document_vectors(self) -> dict[str, NDArray[np.float32]]:
        """One vector per document: the normalized mean of its chunk vectors."""
        with self._lock:
            if self._doc_vectors is None:
                if not len(self.rows):
                    self._doc_vectors = {}
                else:
                    sums = np.add.reduceat(self.rows.vectors, self._doc_starts, axis=0)
                    norms = np.linalg.norm(sums, axis=1, keepdims=True)
                    means = sums / np.where(norms == 0, 1, norms)
                    self._doc_vectors = dict(
                        zip(self._doc_paths, means.astype(np.float32), strict=True)
                    )
            return self._doc_vectors

    def _rank_documents(
        self, scores: NDArray[np.float32], doc_mask: NDArray[np.bool_], limit: int
    ) -> list[tuple[int, int]]:
        """Top documents by their best chunk: [(document index, chunk index)]."""
        best = np.maximum.reduceat(scores, self._doc_starts)
        best = np.where(doc_mask, best, -np.inf)
        top = np.argsort(-best, kind="stable")[:limit]
        out = []
        for d in top:
            if not np.isfinite(best[d]):
                break
            start, end = self._doc_starts[d], self._doc_ends[d]
            out.append((int(d), int(start + np.argmax(scores[start:end]))))
        return out

    def search(
        self,
        query_vector: NDArray[np.float32],
        query: str,
        limit: int,
        allowed_paths: set[str] | None = None,
        reranker: Scorer | None = None,
    ) -> list[SearchHit]:
        """Run the hybrid pipeline described in the module docstring."""
        if not len(self.rows):
            return []
        if allowed_paths is None:
            doc_mask = np.ones(len(self._doc_paths), dtype=bool)
        else:
            doc_mask = np.fromiter(
                (p in allowed_paths for p in self._doc_paths),
                dtype=bool,
                count=len(self._doc_paths),
            )
        if not doc_mask.any():
            return []

        dense_scores = self.rows.vectors @ query_vector
        lexical_scores = self.bm25.scores(query)
        pool = max(CANDIDATES_PER_LIST, limit)
        dense = self._rank_documents(dense_scores, doc_mask, pool)
        doc_lexical = np.maximum.reduceat(lexical_scores, self._doc_starts)
        lexical_mask = doc_mask & (doc_lexical > 0)
        lexical = self._rank_documents(lexical_scores, lexical_mask, pool)

        if reranker is None:
            return self._fuse(dense, lexical, dense_scores, limit)

        pairs: list[tuple[int, int]] = []
        for d in dict.fromkeys(d for d, _ in dense + lexical):
            start, end = int(self._doc_starts[d]), int(self._doc_ends[d])
            order = np.argsort(-dense_scores[start:end])[:CHUNKS_PER_CANDIDATE]
            by_dense = start + order
            by_lexical = start + int(np.argmax(lexical_scores[start:end]))
            chosen = dict.fromkeys([*map(int, by_dense), by_lexical])
            pairs.extend((d, i) for i in chosen)
        scores = reranker.score(query, [self.rows.texts[i] for _, i in pairs])
        best_by_doc: dict[int, tuple[float, int]] = {}
        for (d, i), score in zip(pairs, scores, strict=True):
            if d not in best_by_doc or score > best_by_doc[d][0]:
                best_by_doc[d] = (float(score), i)
        ranked = sorted(best_by_doc.items(), key=lambda kv: -kv[1][0])[:limit]
        return [self._hit(i, score) for _, (score, i) in ranked]

    def _fuse(
        self,
        dense: list[tuple[int, int]],
        lexical: list[tuple[int, int]],
        dense_scores: NDArray[np.float32],
        limit: int,
    ) -> list[SearchHit]:
        fused: dict[int, tuple[float, int]] = {}
        for weight, ranking in zip(RRF_WEIGHTS, (dense, lexical), strict=True):
            for rank, (d, i) in enumerate(ranking):
                score, chunk = fused.get(d, (0.0, i))
                if dense_scores[i] > dense_scores[chunk]:
                    chunk = i
                fused[d] = (score + weight / (RRF_K + rank + 1), chunk)
        ranked = sorted(fused.items(), key=lambda kv: -kv[1][0])[:limit]
        return [self._hit(i, score) for _, (score, i) in ranked]

    def _hit(self, i: int, score: float) -> SearchHit:
        return SearchHit(
            path=self.rows.paths[i],
            line=int(self.rows.lines[i]),
            heading=self.rows.headings[i],
            text=self.rows.texts[i],
            score=score,
        )
