# 15. Skip template text in search

Date: 2026-11-16

## Status

Accepted

Amends [12. Use hybrid chunk search with reranking](0012-use-hybrid-chunk-search-with-reranking.md)

## Context

The 16 evaluation queries of ADR 12 each have one concrete target, so they did not show what happens with broad queries. On a 1,900-file Japanese vault whose daily notes come from a template, broad queries over the daily notes returned template sections instead of anything written that day. For three such queries (top 10 each), template sections took 8, 8 and 0 places:

- Embed-only chunks: a section holding only `![[TASKS#^todo]]` is 21 characters, above the 20-character minimum, so it was indexed
- Checklists: a habit checklist is the same in every note apart from which boxes are ticked and a few numbers; it was indexed once per day
- `search` has no score floor, so when few chunks match a broad query, these fill the remaining places

A related problem: chunks only kept their nearest heading. Sections that a tool adds to every note under one parent heading (for example `## AI comments` with a `###` per comment) could not be told apart from the author's own writing, in results or in filters.

## Decision

- Count a chunk's length without embeds, link targets (a wiki link counts as its alias or note name), URLs, block ids and list or checkbox markers. Chunks under 20 characters are not indexed
- At search time, a chunk whose text recurs in 10 or more documents, ignoring checkbox state, digits and whitespace, is never a candidate. It is computed when the index is loaded (about 0.4 s for 26,000 chunks, once per index generation), so it follows the current vault without extra state
- Keep each chunk's heading path (`section`, top level first) in the store and return it with every result. `search` takes `exclude_sections`: headings whose chunks, at any level, are skipped

Store schema 4; existing stores are rebuilt.

## Consequences

Measured on the vault (same machine, reranker on):

| | Before | After |
|-|-|-|
| Template sections in the top 10 of three broad queries | 8, 8, 0 | 2, 2, 1 |
| 16 queries, target first / in top 5 | 13 / 15 | 13 / 15 |
| Chunks indexed | 27,062 | 26,321 (465 more are skipped at search time) |

- Text that really does repeat across 10 or more documents cannot be found by `search`; one copy of it in a document that is not a template still can. `query` and the `embedding` column are unaffected
- `exclude_sections` has a cost the caller should know about: on this vault, excluding the AI comment sections lost 2 of the 15 targets found in the top 5, because those comments paraphrased the day in words close to the queries. Returning `section` lets a caller keep such passages and recognize them instead
- The thresholds (20 characters, 10 documents) are fixed; three broad queries is a small check
