.PHONY: audit browser-install format format-check lint privacy quality release-check test types

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
	uv run pip-audit --skip-editable \
		--ignore-vuln PYSEC-2026-3552 \
		--ignore-vuln PYSEC-2026-3553 \
		--ignore-vuln PYSEC-2026-3554

privacy:
	bash scripts/check-public-data.sh

quality: format-check lint types test audit privacy

release-check: quality
	bash scripts/check-release-ready.sh
