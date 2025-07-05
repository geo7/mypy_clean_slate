.PHONY: clean requirements
.PHONY: git-stats git-log cloc clean-git
.PHONY: deploy
.PHONY: test
.PHONY: requirements
.PHONY: help

CLOC := cloc

#########
# UTILS #
#########

help:
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST) | sort

clean:
	@find . -path './.venv' -prune -o -type f -name "*.pyc" -delete
	@find . -path './.venv' -prune -o -type d -name "__pycache__" -exec rm -rf {} +
	@find . -path './.venv' -prune -o -type d -name ".pytest_cache" -exec rm -rf {} +
	@find . -path './.venv' -prune -o -type d -name ".mypy_cache" -exec rm -rf {} +
	@find . -path './.venv' -prune -o -type d -name ".ipynb_checkpoints" -exec rm -rf {} +

cloc:
	@echo "Code statistics using cloc:"
	$(CLOC) --exclude-dir=venv .

readme:
	uv run python -m scripts.add_help_to_readme

########
# LINT #
########

pre-commit-run:
	uv run pre-commit run --all-files

mypy:
	uv run mypy --strict .

lint: mypy
	uv run ruff check .
	uv run ruff format . --check
	@$(MAKE) --no-print-directory clean

format: pre-commit-run
	uv run ruff format .
	uv run ruff check . --fix
	@$(MAKE) --no-print-directory clean

########
# UV #
########

uv.lock:
	uv lock --check || uv lock

install: uv.lock
	uv sync --all-extras
	@$(MAKE) --no-print-directory clean

##########
# PYTEST #
##########

test: ## run tests
	uv run pytest -vv --cov=mypy_clean_slate --cov-report=html
	uv run coverage html
	@$(MAKE) --no-print-directory clean
