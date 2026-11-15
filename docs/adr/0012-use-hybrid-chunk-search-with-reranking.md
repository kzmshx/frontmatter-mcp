# 12. Use hybrid chunk search with reranking

Date: 2026-11-15

## Status

Accepted

Amends [8. Integrate semantic search via SQL extension](0008-integrate-semantic-search-via-sql-extension.md)

## Context

Semantic search embedded each file's whole body as one vector and exposed it only through SQL (`embed()` and the `embedding` column). On a 1,900-file Japanese Obsidian vault this rarely found the passage a query was about:

- A daily note mixes many topics, so its single vector matched topics in general rather than the moment a query described
- ruri-v3 is trained with task prefixes (`検索クエリ: ` / `検索文書: `), which were not applied
- Scores bunched into a narrow band (about 0.82-0.90), so thresholds could not separate hits from misses
- Results were paths only, so every hit needed a separate file read

With 16 queries that each have one known target document, the target ranked first for 2 queries and in the top 5 for 6.

## Decision

Index ~400-character chunks split at headings and line breaks, and add a `search` tool that runs a hybrid pipeline:

1. Dense: ruri-v3 chunk embeddings with the recommended prefixes; a document scores as its best chunk
2. Lexical: BM25 over character bigrams (no Japanese tokenizer needed), to catch exact names and phrases
3. Rerank: a cross-encoder (default `hotchpotch/japanese-reranker-xsmall-v2`, MIT) scores the best chunks of the top 20 documents from each list. Without a reranker, weighted reciprocal rank fusion (dense 1.0, lexical 0.5) is used

The tool returns one passage per document with its line number, and accepts a SQL `where` condition on frontmatter. The SQL interface stays: `embedding` becomes the normalized mean of a document's chunk vectors, and `embed()` applies the query prefix.

Alternatives measured on the same 16 queries (target ranked first / in top 5):

| Pipeline | Top 1 | Top 5 |
|----------|-------|-------|
| Whole-document embedding (before) | 2 | 6 |
| Chunk embedding with prefixes | 11 | 14 |
| Bigram BM25 | 11 | 12 |
| Dense + BM25, weighted RRF | 12 | 14 |
| Dense + BM25 + xsmall reranker | 13 | 15 |
| Same with ruri-v3-reranker-310m | 12 | 15 (about 3 s per query) |

## Consequences

- The cache schema changes (files and chunks tables); existing caches are replaced by a new file on the next start. Indexing the 1,900-file vault takes about 90 seconds on an M-series Mac
- The cache file is about 35 MB (the old whole-document cache had grown to 118 MB). DuckDB never shrinks a file, so after indexing it is rewritten once it is 25% (and 8 MB) larger than after its last rewrite
- sentence-transformers, scipy and scikit-learn are imported lazily and indexing starts on the first semantic call. A server that never searches stays at about 110 MB instead of about 470 MB (importing torch); after the first search it uses about 1.1 GB
- The reranker model is downloaded on the first search and adds about 0.3 seconds per query; `FRONTMATTER_RERANKER_MODEL=""` turns it off
- scikit-learn and scipy become direct dependencies of the `semantic` extra (they were already installed through sentence-transformers)
- The `vss` extension is no longer installed; `array_cosine_similarity` is built into DuckDB
- 16 queries chosen by the author is a small evaluation; the ordering of the pipelines is indicative, not a benchmark
