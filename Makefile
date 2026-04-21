# ──────────────────────────────────────────────────────────────────────
# PrasWord — Makefile
# ──────────────────────────────────────────────────────────────────────
.PHONY: help install install-all run run-debug test test-fast lint typecheck clean

PYTHON   ?= python3
PIP      ?= pip
PYTEST   ?= $(PYTHON) -m pytest
QT_PLAT  ?= offscreen
VENV     ?= .venv

help:                  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*##"}{printf "  \033[36m%-18s\033[0m %s\n",$$1,$$2}'

$(VENV)/bin/activate:  ## Create virtualenv (auto)
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip --quiet

install: $(VENV)/bin/activate  ## Install core deps in venv
	$(VENV)/bin/pip install -e . --quiet
	@echo "✓ PrasWord installed. Run: make run"

install-all: $(VENV)/bin/activate  ## Install all extras + dev tools
	$(VENV)/bin/pip install -e ".[all,dev]" --quiet
	@echo "✓ PrasWord + all extras installed."

run:                   ## Launch PrasWord (requires install)
	$(PYTHON) -m prasword

run-debug:             ## Launch with DEBUG logging
	PRASWORD_LOG_LEVEL=DEBUG $(PYTHON) -m prasword

run-script:            ## Launch via run.py (no pip install needed)
	$(PYTHON) run.py

test:                  ## Run full test suite (headless Qt)
	QT_QPA_PLATFORM=$(QT_PLAT) $(PYTEST) tests/ -v

test-fast:             ## Run tests, stop on first failure
	QT_QPA_PLATFORM=$(QT_PLAT) $(PYTEST) tests/ -x -q

lint:                  ## Run ruff linter
	$(PYTHON) -m ruff check prasword/

lint-fix:              ## Auto-fix ruff issues
	$(PYTHON) -m ruff check prasword/ --fix

typecheck:             ## Run mypy
	$(PYTHON) -m mypy prasword/

clean:                 ## Remove bytecode, caches, build artefacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache dist build *.egg-info prasword.egg-info
