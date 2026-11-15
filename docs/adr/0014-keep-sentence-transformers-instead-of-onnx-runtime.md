# 14. Keep sentence-transformers instead of ONNX Runtime

Date: 2026-11-16

## Status

Accepted

## Context

The `semantic` extra installs sentence-transformers, which pulls in torch. The environment is about 1.3 GB, and importing torch alone takes about 470 MB of memory ([12. Use hybrid chunk search with reranking](0012-use-hybrid-chunk-search-with-reranking.md)). Both models could run on ONNX Runtime instead, with `tokenizers` for tokenization and no torch:

- Embedding model (`cl-nagoya/ruri-v3-30m`, Apache-2.0): no ONNX file is published. It was exported with `torch.onnx.export` (TorchScript exporter, opset 17, eager attention, dynamic batch and sequence axes), with mean pooling and L2 normalization done in numpy. The output matched sentence-transformers (cosine similarity 1.0, including padded batches). Dynamic int8 quantization shrinks the file from 140 MB to 35 MB
- Reranker (`hotchpotch/japanese-reranker-xsmall-v2`, MIT): the model repository already ships `onnx/model.onnx` and an int8 variant

The three backends were compared on a 1,900-file Japanese vault with the 16 queries from ADR 12, on an M-series Mac:

| Backend | Full index | Per search | Top 1 / Top 5 | RSS after searches | Install size |
|---------|------------|------------|---------------|--------------------|--------------|
| sentence-transformers (MPS) | 80 s | 0.28-0.37 s | 13 / 15 | about 1.1 GB | about 1.3 GB |
| ONNX Runtime fp32 (CPU) | 457 s | 1.9 s | 13 / 15 | about 1.4 GB | about 0.5 GB |
| ONNX Runtime int8 (CPU) | 263 s | 1.1 s | 13 / 15 (one target moved from 2nd to 3rd) | about 1.5 GB | about 0.5 GB |

- sentence-transformers runs both models on the GPU through MPS; ONNX Runtime runs on the CPU
- With its default CPU memory arena, ONNX Runtime fp32 reached 3.8-4.4 GB of RSS. The table shows it with the arena disabled
- RSS may not include memory MPS holds on the GPU, so the memory comparison is approximate
- The CoreML execution provider failed to build a model from the exported graph (610 of 736 nodes supported, 43 partitions)

## Decision

Keep sentence-transformers (torch) as the only backend. ONNX Runtime gives the same search quality, but on the Mac this server runs on it is 3-7 times slower and does not use less memory. Its only gain is a smaller install.

## Consequences

- The `semantic` extra keeps depending on torch, so installing it stays at about 1.3 GB
- Revisit if the server needs to run where torch has no GPU backend (for example a small Linux machine), or if the CoreML execution provider can run the exported embedding model. The export recipe above reproduces the ONNX model
- 16 queries on one vault is a small evaluation; speeds depend on the machine
