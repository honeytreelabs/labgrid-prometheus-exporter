PYTHON ?= uv run

.PHONY: help install install-python install-hooks pre-commit test lint format format-check typecheck build clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-24s\033[0m %s\n", $$1, $$2}'

install: install-python install-hooks ## Install dependencies and Git hooks

install-python: ## Install Python dependencies
	uv sync

install-hooks: ## Install pre-commit hooks
	$(PYTHON) pre-commit install

pre-commit: ## Run pre-commit hooks on tracked and untracked files
	$(PYTHON) pre-commit run --files $$(git ls-files --cached --others --exclude-standard)

test: ## Run Python tests
	$(PYTHON) pytest

lint: ## Run Python lint checks
	$(PYTHON) ruff check .

format: ## Format Python code
	$(PYTHON) ruff format .

format-check: ## Check Python code formatting
	$(PYTHON) ruff format --check .

type-check: ## Run Python type checks
	$(PYTHON) ty check

build: ## Build Python package artifacts
	uv build

clean: ## Remove local test/build artifacts
	find . -type d \( -name .pytest_cache -o -name .ruff_cache -o -name htmlcov -o -name build -o -name dist -o -name '*.egg-info' \) -prune -exec rm -r {} +
