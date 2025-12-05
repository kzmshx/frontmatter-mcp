.PHONY: help
help: ## Show help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

.PHONY: lint
lint: ## Run linter
	uv run ruff check src tests
	uv run ruff format --check src tests

.PHONY: fix
fix: ## Auto-fix lint issues
	uv run ruff check --fix src tests
	uv run ruff format src tests

.PHONY: test
test: ## Run all tests
	uv run pytest tests -v

.PHONY: test-fast
test-fast: ## Run tests excluding slow tests
	uv run pytest tests -v -m "not slow"
