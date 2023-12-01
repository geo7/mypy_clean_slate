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
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type d -name ".pytest_cache" -exec rm -rf {} +
	@find . -type d -name ".mypy_cache" -exec rm -rf {} +
	@find . -type d -name ".ipynb_checkpoints" -exec rm -rf {} +

cloc:
	@echo "Code statistics using cloc:"
	$(CLOC) --exclude-dir=venv .

########
# LINT #
########

pre-commit-run:
	poetry run pre-commit run --all-files

lint:
	poetry run ruff check .
	poetry run ruff format . --check
	@$(MAKE) --no-print-directory clean

format: pre-commit-run
	poetry run ruff format .
	poetry run ruff check . --fix
	@$(MAKE) --no-print-directory clean

##########
# POETRY #
##########

poetry.lock:
	poetry lock --no-update

install: poetry.lock
	poetry install
	@$(MAKE) --no-print-directory clean

##########
# PYTEST #
##########

test: ## run tests
	poetry run pytest --cov=mypy_clean_slate --cov-report=html
	poetry run coverage html
	@$(MAKE) --no-print-directory clean
