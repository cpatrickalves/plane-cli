.DEFAULT_GOAL := help

.PHONY: help install install-tool sync test test-v lint lint-fix format check build clean run

# ──────────────────────────────────────────────
# Setup
# ──────────────────────────────────────────────

install: ## Install dependencies (dev environment)
	@echo "install - Install dependencies (dev environment)"
	uv sync

install-tool: ## Install CLI system-wide (editable)
	@echo "install-tool - Install CLI system-wide (editable)"
	uv tool install -e .

sync: install ## Alias for install

# ──────────────────────────────────────────────
# Development
# ──────────────────────────────────────────────

run: ## Run the CLI (pass ARGS="--help" for options)
	@echo "run - Run the CLI"
	uv run planecli $(ARGS)

# ──────────────────────────────────────────────
# Quality
# ──────────────────────────────────────────────

test: ## Run tests
	@echo "test - Run all tests"
	uv run pytest tests/

test-v: ## Run tests (verbose)
	@echo "test-v - Run all tests (verbose)"
	uv run pytest tests/ -v

lint: ## Run linter
	@echo "lint - Run linter using ruff"
	uv run ruff check src/

lint-fix: ## Run linter with auto-fix
	@echo "lint-fix - Run linter with auto-fix"
	uv run ruff check --fix src/

format: ## Format code using ruff formatter
	@echo "format - Format code using ruff formatter"
	uv run ruff format src/ tests/

check: lint test ## Run lint + tests

# ──────────────────────────────────────────────
# Build & Clean
# ──────────────────────────────────────────────

build: ## Build distribution packages
	@echo "build - Build distribution packages"
	uv build

clean: ## Remove build artifacts and caches
	@echo "clean - Remove build artifacts and caches"
	rm -rf dist/ build/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true

# ──────────────────────────────────────────────
# Help
# ──────────────────────────────────────────────

help: ## Show available commands
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
