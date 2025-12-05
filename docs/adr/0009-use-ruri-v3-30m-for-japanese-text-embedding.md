# 9. Use ruri-v3-30m for Japanese text embedding

Date: 2025-12-05

## Status

Accepted

## Context

Semantic search requires an embedding model to convert text into vectors. The primary use case is searching Japanese Markdown notes (e.g., Obsidian vault).

Requirements:

- Japanese language support with high quality
- Lightweight for local execution on consumer hardware (e.g., M1 Mac)
- No external API calls (zero cost, offline capable)

Models considered:

| Model | Parameters | JMTEB Score | Notes |
|-------|------------|-------------|-------|
| cl-nagoya/ruri-v3-30m | 30M | 72.95 | Japanese-specialized |
| multilingual-e5-small | 118M | 67.38 | Multilingual |
| multilingual-e5-base | 278M | 70.53 | Multilingual |

## Decision

Adopted cl-nagoya/ruri-v3-30m as the default embedding model.

Key factors:

- Highest JMTEB score (72.95) among lightweight models
- Smallest parameter count (30M) enables fast inference
- 256-dimensional output balances quality and storage efficiency
- Japanese-specialized training data

The model is configurable via `FRONTMATTER_EMBEDDING_MODEL` environment variable for users who prefer different models.

## Consequences

Benefits:

- Fast embedding generation even on CPU
- Small model download size (~120MB)
- High quality Japanese text understanding

Trade-offs:

- Optimized for Japanese; may underperform for other languages
- Smaller dimension (256) compared to larger models (768+) may lose some nuance
- Users with multilingual notes may need to switch models
