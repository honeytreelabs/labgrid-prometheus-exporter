PYTHON ?= uv run

# grpc and wamp are mutually exclusive workspace members (see [tool.uv]
# conflicts in the root pyproject.toml: they require incompatible labgrid
# ranges), so there is no single synced environment containing both. Targets
# that need real imports (test, type-check, install) loop over each variant,
# syncing only core + meta + that one backend each time.
BACKENDS := grpc wamp

.PHONY: help install install-python install-hooks pre-commit test test-integration lint format format-check type-check build clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-24s\033[0m %s\n", $$1, $$2}'

install: install-python install-hooks ## Install dependencies and Git hooks

install-python: ## Install Python dependencies for each backend variant
	@set -e; for backend in $(BACKENDS); do \
		echo "--- syncing $$backend backend ---"; \
		uv sync --package labgrid-prometheus-exporter-core --package labgrid-prometheus-exporter \
			--package labgrid-prometheus-exporter-backend-$$backend; \
	done

install-hooks: ## Install pre-commit hooks
	$(PYTHON) --no-sync pre-commit install

pre-commit: ## Run pre-commit hooks on tracked and untracked files
	$(PYTHON) --no-sync pre-commit run --files $$(git ls-files --cached --others --exclude-standard)

test: ## Run Python tests for each backend variant
	@set -e; for backend in $(BACKENDS); do \
		echo "--- testing $$backend backend ---"; \
		uv sync --package labgrid-prometheus-exporter-core --package labgrid-prometheus-exporter \
			--package labgrid-prometheus-exporter-backend-$$backend; \
		uv run --no-sync pytest packages/core packages/meta packages/backend-$$backend; \
	done

test-integration: ## Run Docker-based integration tests for each backend variant (slow; not run by `make test` or pre-commit)
	@set -e; for backend in $(BACKENDS); do \
		echo "--- integration-testing $$backend backend ---"; \
		uv sync --package labgrid-prometheus-exporter-core --package labgrid-prometheus-exporter \
			--package labgrid-prometheus-exporter-backend-$$backend; \
		LG_PROMETHEUS_EXPORTER_TEST_VARIANT=$$backend uv run --no-sync pytest tests/integration; \
	done

## ruff is pure static analysis (no imports resolved against installed
## packages), so it doesn't care which backend variant, if any, is synced.
## --no-sync avoids `uv run` re-resolving the whole (conflicting) workspace.

lint: ## Run Python lint checks
	uv run --no-sync ruff check .

format: ## Format Python code
	uv run --no-sync ruff format .

format-check: ## Check Python code formatting
	uv run --no-sync ruff format --check .

type-check: ## Run Python type checks for each backend variant
	@set -e; for backend in $(BACKENDS); do \
		echo "--- type-checking $$backend backend ---"; \
		uv sync --package labgrid-prometheus-exporter-core --package labgrid-prometheus-exporter \
			--package labgrid-prometheus-exporter-backend-$$backend; \
		uv run --no-sync ty check packages/core packages/meta packages/backend-$$backend tests/integration; \
	done

build: ## Build Python package artifacts
	uv build --all-packages

clean: ## Remove local test/build artifacts
	find . -type d \( -name .pytest_cache -o -name .ruff_cache -o -name htmlcov -o -name build -o -name dist -o -name '*.egg-info' \) -prune -exec rm -r {} +
