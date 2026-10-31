.PHONY: audit browser-install docs format format-check lint privacy quality quality-fast release-check test types

browser-install:
	uv run playwright install chromium

format:
	uv run ruff format .
	uv run ruff check --fix .

format-check:
	uv run ruff format --check .

lint:
	uv run ruff check .

types:
	uv run mypy

test:
	uv run pytest --cov --cov-branch --cov-report=term-missing --cov-report=json
	uv run python scripts/check_coverage.py

audit:
	uv run python scripts/check_security_exceptions.py
	uv run pip-audit --skip-editable

privacy:
	bash scripts/check-public-data.sh

docs:
	uv run python scripts/check_doc_links.py

quality-fast: format-check lint types docs privacy

quality: format-check lint types test docs audit privacy

release-check: quality
	bash scripts/check-release-ready.sh
