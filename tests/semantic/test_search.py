"""Tests for the hybrid search index."""

import numpy as np

from frontmatter_mcp.semantic.search import Bm25Index, SearchIndex
from frontmatter_mcp.semantic.store import ChunkRows

DIM = 4


def _rows(items: list[tuple[str, str, list[float]]]) -> ChunkRows:
    vecs = np.array([v for _, _, v in items], dtype=np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    return ChunkRows(
        paths=[p for p, _, _ in items],
        lines=np.arange(1, len(items) + 1),
        headings=["h"] * len(items),
        texts=[t for _, t, _ in items],
        vectors=vecs,
        sections=[["h"] for _ in items],
    )


ROWS = _rows(
    [
        ("a.md", "河井寛次郎記念館で陶芸を見た", [1, 0, 0, 0]),
        ("a.md", "その後に喫茶店へ寄った", [0.9, 0.1, 0, 0]),
        ("b.md", "ダーツが入らず苛立った", [0, 1, 0, 0]),
        ("c.md", "寝間着が暑くて目覚めが悪い", [0, 0, 1, 0]),
    ]
)


class FakeReranker:
    """Scores a text by how many query characters it contains."""

    def score(self, query: str, texts: list[str]) -> np.ndarray:
        return np.array([sum(ch in t for ch in query) for t in texts], np.float32)


def test_bm25_prefers_matching_bigrams() -> None:
    bm25 = Bm25Index(ROWS.texts)
    scores = bm25.scores("ダーツ")
    assert int(np.argmax(scores)) == 2
    assert scores[0] == 0


def test_dense_only_match_is_found() -> None:
    """A query with no shared wording still finds the document by meaning."""
    index = SearchIndex(ROWS)
    hits = index.search(np.array([0, 0, 1, 0], np.float32), "パジャマ", 2)
    assert hits[0].path == "c.md"


def test_one_hit_per_document_with_best_chunk() -> None:
    index = SearchIndex(ROWS)
    hits = index.search(np.array([1, 0, 0, 0], np.float32), "陶芸", 3)
    paths = [h.path for h in hits]
    assert paths[0] == "a.md"
    assert len(paths) == len(set(paths))
    assert hits[0].line == 1


def test_allowed_paths_filter() -> None:
    index = SearchIndex(ROWS)
    hits = index.search(
        np.array([1, 0, 0, 0], np.float32), "陶芸", 5, allowed_paths={"b.md"}
    )
    assert [h.path for h in hits] == ["b.md"]


def test_reranker_decides_order() -> None:
    index = SearchIndex(ROWS)
    # Dense points at a.md, but the reranker favors the text containing the query
    hits = index.search(
        np.array([1, 0, 0, 0], np.float32),
        "ダーツ苛立",
        3,
        reranker=FakeReranker(),
    )
    assert hits[0].path == "b.md"


def test_empty_index() -> None:
    empty = _rows([("x.md", "placeholder text", [1, 0, 0, 0])])
    index = SearchIndex(empty)
    assert index.search(np.ones(DIM, np.float32), "q", 3, allowed_paths=set()) == []


def test_result_text_is_truncated() -> None:
    long_rows = _rows([("a.md", "あ" * 2000, [1, 0, 0, 0])])
    hit = SearchIndex(long_rows).search(np.array([1, 0, 0, 0], np.float32), "あ", 1)[0]
    assert len(hit.to_dict()["text"]) <= 801


def test_text_repeated_across_documents_is_not_returned() -> None:
    """A template checklist in every note never crowds out real passages."""
    from frontmatter_mcp.semantic.search import REPEATED_MIN_DOCUMENTS

    n = REPEATED_MIN_DOCUMENTS
    template = [
        (
            f"d{i:02d}.md",
            f"Tracking\n- [{'x' if i % 2 else ' '}] walk {i} steps",
            [1, 0, 0, 0],
        )
        for i in range(n)
    ]
    rows = _rows([*template, ("own.md", "a walk by the river", [0.5, 0.5, 0, 0])])
    hits = SearchIndex(rows).search(np.array([1, 0, 0, 0], np.float32), "walk", 5)
    assert [h.path for h in hits] == ["own.md"]


def test_text_in_a_few_documents_is_kept() -> None:
    from frontmatter_mcp.semantic.search import REPEATED_MIN_DOCUMENTS

    items = [
        (f"d{i}.md", "same text", [1, 0, 0, 0])
        for i in range(REPEATED_MIN_DOCUMENTS - 1)
    ]
    hits = SearchIndex(_rows(items)).search(
        np.array([1, 0, 0, 0], np.float32), "same", 20
    )
    assert len(hits) == REPEATED_MIN_DOCUMENTS - 1


def test_exclude_sections_skips_chunks_under_a_heading() -> None:
    rows = _rows(
        [
            ("a.md", "comment on the walk", [1, 0, 0, 0]),
            ("a.md", "I walked by the river", [0.6, 0.4, 0, 0]),
            ("b.md", "comment on dinner", [0.9, 0.1, 0, 0]),
        ]
    )
    rows.sections = [["Day", "AI comments", "Walk"], ["Day", "Log"], ["AI comments"]]
    index = SearchIndex(rows)
    query = np.array([1, 0, 0, 0], np.float32)
    for reranker in (None, FakeReranker()):
        hits = index.search(
            query, "walk", 5, reranker=reranker, exclude_sections=["AI comments"]
        )
        assert [(h.path, h.line) for h in hits] == [("a.md", 2)]
        assert hits[0].to_dict()["section"] == ["Day", "Log"]
