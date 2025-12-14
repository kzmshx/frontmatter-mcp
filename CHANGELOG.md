# Changelog

## [0.5.1](https://github.com/kzmshx/frontmatter-mcp/compare/v0.5.0...v0.5.1) (2025-12-14)


### Bug Fixes

* use read-only connection for semantic query to avoid DuckDB lock conflicts ([#43](https://github.com/kzmshx/frontmatter-mcp/issues/43)) ([66f0baa](https://github.com/kzmshx/frontmatter-mcp/commit/66f0baa37d7f3ab045ffa7ecac32d96af947f119)), closes [#42](https://github.com/kzmshx/frontmatter-mcp/issues/42)


### Documentation

* translate CLAUDE.md and SETUP.md to English ([#39](https://github.com/kzmshx/frontmatter-mcp/issues/39)) ([c5fc96a](https://github.com/kzmshx/frontmatter-mcp/commit/c5fc96a32d71a2fa770c44fce9d9c092348d9e67))

## [0.5.0](https://github.com/kzmshx/frontmatter-mcp/compare/v0.4.4...v0.5.0) (2025-12-07)


### Features

* add batch_array_unique tool to remove duplicates from arrays ([#37](https://github.com/kzmshx/frontmatter-mcp/issues/37)) ([b336c34](https://github.com/kzmshx/frontmatter-mcp/commit/b336c346a4fbb2e0623f472913a47e6948fb7243))

## [0.4.4](https://github.com/kzmshx/frontmatter-mcp/compare/v0.4.3...v0.4.4) (2025-12-07)


### Bug Fixes

* close cache connection after indexing to prevent DuckDB lock conflicts ([#35](https://github.com/kzmshx/frontmatter-mcp/issues/35)) ([26c68bc](https://github.com/kzmshx/frontmatter-mcp/commit/26c68bc86f92bec1e58cf96210e8dcfff7d726db))

## [0.4.3](https://github.com/kzmshx/frontmatter-mcp/compare/v0.4.2...v0.4.3) (2025-12-06)


### Bug Fixes

* remove indexed_count from index_status and index_wait responses ([#34](https://github.com/kzmshx/frontmatter-mcp/issues/34)) ([d5928f5](https://github.com/kzmshx/frontmatter-mcp/commit/d5928f5ff8a8beb2e7bc6c71aef490d95bac74b6))


### Performance

* add mtime-based in-memory cache for parse_files ([#33](https://github.com/kzmshx/frontmatter-mcp/issues/33)) ([c902d24](https://github.com/kzmshx/frontmatter-mcp/commit/c902d24b909702f40e3c26d1e095e10fe28186bc))
* use PyArrow bulk insert for semantic embeddings ([#31](https://github.com/kzmshx/frontmatter-mcp/issues/31)) ([4a13ac7](https://github.com/kzmshx/frontmatter-mcp/commit/4a13ac73d5a827a919459d47bf3be56c8d4dfcf8))

## [0.4.2](https://github.com/kzmshx/frontmatter-mcp/compare/v0.4.1...v0.4.2) (2025-12-06)


### Bug Fixes

* trigger release for publish workflow fix ([#28](https://github.com/kzmshx/frontmatter-mcp/issues/28)) ([b9dcb70](https://github.com/kzmshx/frontmatter-mcp/commit/b9dcb709bf91be64d085711817b33ee817e73da7))

## [0.4.1](https://github.com/kzmshx/frontmatter-mcp/compare/v0.4.0...v0.4.1) (2025-12-06)


### Bug Fixes

* **ci:** use venv instead of --system for TestPyPI install test ([#25](https://github.com/kzmshx/frontmatter-mcp/issues/25)) ([7ed62ab](https://github.com/kzmshx/frontmatter-mcp/commit/7ed62ab8787d478c0251eac0d66c885dce74113c))

## [0.4.0](https://github.com/kzmshx/frontmatter-mcp/compare/v0.3.0...v0.4.0) (2025-12-06)


### Features

* add index_wait tool for blocking wait on indexing completion ([#24](https://github.com/kzmshx/frontmatter-mcp/issues/24)) ([4ad03fd](https://github.com/kzmshx/frontmatter-mcp/commit/4ad03fd836129ab0276a85a567e5a5411d9137f4))


### Bug Fixes

* avoid DB lock in index_status by caching indexed count in memory ([#19](https://github.com/kzmshx/frontmatter-mcp/issues/19)) ([73f6e28](https://github.com/kzmshx/frontmatter-mcp/commit/73f6e28301faf4f2b66bd6793469994b2aacf839))


### Documentation

* add semantic search usage guide to query tool description ([#20](https://github.com/kzmshx/frontmatter-mcp/issues/20)) ([59e1ace](https://github.com/kzmshx/frontmatter-mcp/commit/59e1ace0ce66df39c769b11f3618d3fb93887755))

## [0.3.0](https://github.com/kzmshx/frontmatter-mcp/compare/v0.2.1...v0.3.0) (2025-12-06)


### Features

* add semantic search with local embedding model ([#16](https://github.com/kzmshx/frontmatter-mcp/issues/16)) ([4316479](https://github.com/kzmshx/frontmatter-mcp/commit/43164795c344992652d49fe20dce73cab7f1eff7))

## [0.2.1](https://github.com/kzmshx/frontmatter-mcp/compare/v0.2.0...v0.2.1) (2025-11-29)


### Documentation

* update README with uvx configuration ([#12](https://github.com/kzmshx/frontmatter-mcp/issues/12)) ([3aa60d4](https://github.com/kzmshx/frontmatter-mcp/commit/3aa60d4d47ff9bb85181fb04b15f5dfefbb92020))

## [0.2.0](https://github.com/kzmshx/frontmatter-mcp/compare/v0.1.0...v0.2.0) (2025-11-29)


### ⚠ BREAKING CHANGES

* Tool names have changed
    - inspect_frontmatter -> query_inspect
    - query_frontmatter -> query
    - update_frontmatter -> update

### Features

* add batch array tools for array property operations ([#6](https://github.com/kzmshx/frontmatter-mcp/issues/6)) ([04d46a9](https://github.com/kzmshx/frontmatter-mcp/commit/04d46a988400b58c5776728454f17a19a3ed976b))
* add batch_update tool ([#5](https://github.com/kzmshx/frontmatter-mcp/issues/5)) ([a5b2bcf](https://github.com/kzmshx/frontmatter-mcp/commit/a5b2bcfb6b637444766518c1ac355c8531703f40))
* add MIT License to the project ([4618791](https://github.com/kzmshx/frontmatter-mcp/commit/4618791cdae128494000d856eac90d4cad3fd353))
* add update_frontmatter tool ([#1](https://github.com/kzmshx/frontmatter-mcp/issues/1)) ([d53b16b](https://github.com/kzmshx/frontmatter-mcp/commit/d53b16b376d9e49664e543701bd3491baec30af1))
* implement MCP server with inspect and query tools ([c64a5cb](https://github.com/kzmshx/frontmatter-mcp/commit/c64a5cb438a9b4c5f5fcea14380a57f9f1eab7b0))
* rename tools for better naming convention ([#4](https://github.com/kzmshx/frontmatter-mcp/issues/4)) ([1458c5f](https://github.com/kzmshx/frontmatter-mcp/commit/1458c5f57fcf90f9d72aff22d6e971b99d8a47d1))


### Bug Fixes

* output Unicode directly instead of escape sequences ([56c96d2](https://github.com/kzmshx/frontmatter-mcp/commit/56c96d298655fd30bd73535dccf0952870fde14b))
* return dict instead of JSON string from tools ([#3](https://github.com/kzmshx/frontmatter-mcp/issues/3)) ([c34b399](https://github.com/kzmshx/frontmatter-mcp/commit/c34b3996e6b434b769127e65fc01cf3290a06238))


### Documentation

* add architecture decision records ([50c1809](https://github.com/kzmshx/frontmatter-mcp/commit/50c1809db4645de11c3be71a9d5e1a4b89a99cab))
* add PR review commands to CLAUDE.md ([#10](https://github.com/kzmshx/frontmatter-mcp/issues/10)) ([1df3391](https://github.com/kzmshx/frontmatter-mcp/commit/1df33918dc70d0b233c36058946f43527e33e3e1))
* add README with installation and usage guide ([790a313](https://github.com/kzmshx/frontmatter-mcp/commit/790a3138e207f7c906e98541d2516b52266a3c41))
* add shared documentation rules to CLAUDE.md ([3aac2bb](https://github.com/kzmshx/frontmatter-mcp/commit/3aac2bb5fc93630baaaeeb05866eefc4c71c0dd1))
* improve README with clear tool documentation ([40202c1](https://github.com/kzmshx/frontmatter-mcp/commit/40202c1f3400ecd31df11f114e0262e9940b6457))
* translate all documentation to English ([1a24138](https://github.com/kzmshx/frontmatter-mcp/commit/1a241384b1e8da81aecec8a9fe859d0d13142b77))
* update README with new tool names and batch tools ([#7](https://github.com/kzmshx/frontmatter-mcp/issues/7)) ([08c5ce7](https://github.com/kzmshx/frontmatter-mcp/commit/08c5ce7c8dd68462628912e4962cb53063f85323))

## Changelog
