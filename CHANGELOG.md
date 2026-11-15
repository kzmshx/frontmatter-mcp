# Changelog

## [0.7.0](https://github.com/kzmshx/frontmatter-mcp/compare/v0.6.2...v0.7.0) (2026-11-15)


### Features

* exclude files from every tool with FRONTMATTER_EXCLUDE ([#77](https://github.com/kzmshx/frontmatter-mcp/issues/77)) ([3f1ec30](https://github.com/kzmshx/frontmatter-mcp/commit/3f1ec302f47538aae05fa73f1c70ae419e771370))
* skip template text in search and return each passage's heading path ([#78](https://github.com/kzmshx/frontmatter-mcp/issues/78)) ([7785ace](https://github.com/kzmshx/frontmatter-mcp/commit/7785ace9219304e683f1959994bc8cb4e909e543))


### Bug Fixes

* answer --version and --help without reading settings ([#76](https://github.com/kzmshx/frontmatter-mcp/issues/76)) ([3ccdc32](https://github.com/kzmshx/frontmatter-mcp/commit/3ccdc3280c2a4347065f6f64f773b402f0eabc6a))

## [0.6.2](https://github.com/kzmshx/frontmatter-mcp/compare/v0.6.1...v0.6.2) (2026-11-15)


### Documentation

* record why ONNX Runtime was not adopted ([#74](https://github.com/kzmshx/frontmatter-mcp/issues/74)) ([0d8f55c](https://github.com/kzmshx/frontmatter-mcp/commit/0d8f55c97ea1c450c09dce0ae09d923dd25a20ac))

## [0.6.1](https://github.com/kzmshx/frontmatter-mcp/compare/v0.6.0...v0.6.1) (2026-11-15)


### Bug Fixes

* report and use the index a search serves before the first run ends ([#72](https://github.com/kzmshx/frontmatter-mcp/issues/72)) ([bf82d36](https://github.com/kzmshx/frontmatter-mcp/commit/bf82d365c43ac6b6608917fb23911f4516409012))

## [0.6.0](https://github.com/kzmshx/frontmatter-mcp/compare/v0.5.6...v0.6.0) (2026-11-15)


### Features

* add hybrid search over chunks with reranking ([#67](https://github.com/kzmshx/frontmatter-mcp/issues/67)) ([e811ce4](https://github.com/kzmshx/frontmatter-mcp/commit/e811ce42358178be8e8abcf2d472c21b1e24d8c8))
* publish output schemas, report warnings as {path, error}, and explain SQL errors ([1907aea](https://github.com/kzmshx/frontmatter-mcp/commit/1907aead22b9a8e768a60ce38f575c378785b258))


### Bug Fixes

* act on every occurrence in batch_array_remove and batch_array_replace ([1907aea](https://github.com/kzmshx/frontmatter-mcp/commit/1907aead22b9a8e768a60ce38f575c378785b258))
* ignore a frontmatter key named path instead of replacing the file path ([1907aea](https://github.com/kzmshx/frontmatter-mcp/commit/1907aead22b9a8e768a60ce38f575c378785b258))
* leave files whose frontmatter would not change untouched ([1907aea](https://github.com/kzmshx/frontmatter-mcp/commit/1907aead22b9a8e768a60ce38f575c378785b258))
* make the default install (without [semantic]) start ([#70](https://github.com/kzmshx/frontmatter-mcp/issues/70)) ([44f4a50](https://github.com/kzmshx/frontmatter-mcp/commit/44f4a500d55b6178b06b00dcedbc479585916d0b))
* rewrite only the frontmatter keys that change ([#66](https://github.com/kzmshx/frontmatter-mcp/issues/66)) ([ff43259](https://github.com/kzmshx/frontmatter-mcp/commit/ff4325951617d10e3570dc2016800c16faf4ba29))
* stop interpreting glob characters in the base directory ([1907aea](https://github.com/kzmshx/frontmatter-mcp/commit/1907aead22b9a8e768a60ce38f575c378785b258))


### Performance

* speed up query and search, and make indexing state and errors visible ([#69](https://github.com/kzmshx/frontmatter-mcp/issues/69)) ([491b17d](https://github.com/kzmshx/frontmatter-mcp/commit/491b17debc38b488f73c34d5a8e984ee2ce87d4f))


### Refactoring

* organize modules by responsibility ([1907aea](https://github.com/kzmshx/frontmatter-mcp/commit/1907aead22b9a8e768a60ce38f575c378785b258))

## [0.5.6](https://github.com/kzmshx/frontmatter-mcp/compare/v0.5.5...v0.5.6) (2026-11-15)


### Bug Fixes

* **deps:** Bump the "weekly" group with 2 updates across multiple ecosystems ([#64](https://github.com/kzmshx/frontmatter-mcp/issues/64)) ([54e6bcc](https://github.com/kzmshx/frontmatter-mcp/commit/54e6bccb481c974db04501d8bb0c00eaa8d272c3))

## [0.5.5](https://github.com/kzmshx/frontmatter-mcp/compare/v0.5.4...v0.5.5) (2026-11-15)


### Bug Fixes

* **deps:** bump duckdb from 1.5.6 to 2.0.0 ([#59](https://github.com/kzmshx/frontmatter-mcp/issues/59)) ([399f263](https://github.com/kzmshx/frontmatter-mcp/commit/399f263829bcb032c888f71c9c634f3cbc0fd95d))
* **deps:** bump pyarrow from 25.0.1 to 26.0.1 ([#58](https://github.com/kzmshx/frontmatter-mcp/issues/58)) ([f93cb47](https://github.com/kzmshx/frontmatter-mcp/commit/f93cb4726391040dfdb049072d776cf1731ca45a))
* pass read-only tool annotations as a dict so they type-check on FastMCP 4 ([#61](https://github.com/kzmshx/frontmatter-mcp/issues/61)) ([adc6fc4](https://github.com/kzmshx/frontmatter-mcp/commit/adc6fc4e98e97bd208e382d9fc28fcfbe66d1146))

## [0.5.4](https://github.com/kzmshx/frontmatter-mcp/compare/v0.5.3...v0.5.4) (2026-11-15)


### Bug Fixes

* block file, network, and extension access from query SQL ([#51](https://github.com/kzmshx/frontmatter-mcp/issues/51)) ([8a55da3](https://github.com/kzmshx/frontmatter-mcp/commit/8a55da318699f9ed0feb7a3c1223c916850947c8))
* **deps:** require FastMCP 3.2+ for security fixes ([8a55da3](https://github.com/kzmshx/frontmatter-mcp/commit/8a55da318699f9ed0feb7a3c1223c916850947c8))
* write files atomically so a failed update no longer empties them ([#50](https://github.com/kzmshx/frontmatter-mcp/issues/50)) ([8a55da3](https://github.com/kzmshx/frontmatter-mcp/commit/8a55da318699f9ed0feb7a3c1223c916850947c8))

## [0.5.3](https://github.com/kzmshx/frontmatter-mcp/compare/v0.5.2...v0.5.3) (2025-12-31)


### Documentation

* add MCP_TIMEOUT configuration for semantic search ([#48](https://github.com/kzmshx/frontmatter-mcp/issues/48)) ([27e2858](https://github.com/kzmshx/frontmatter-mcp/commit/27e28582be593a43eb15d8a31bbaffcbe1fc1d67))

## [0.5.2](https://github.com/kzmshx/frontmatter-mcp/compare/v0.5.1...v0.5.2) (2025-12-24)


### Refactoring

* use FastMCP Depends for dependency injection ([#45](https://github.com/kzmshx/frontmatter-mcp/issues/45)) ([346e634](https://github.com/kzmshx/frontmatter-mcp/commit/346e63451a5fc154e767133fda36615b921daa93))

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
