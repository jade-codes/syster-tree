.PHONY: install install-cli dev test lint typecheck format clean all

all: lint typecheck test

install-cli:
	cargo install --path ../cli

install:
	pip install .

dev:
	pip install -e ".[dev]"

test:
	pytest -v

test-cov:
	pytest --cov=systree --cov-report=term-missing

lint:
	ruff check src tests

lint-fix:
	ruff check --fix src tests

typecheck:
	mypy src

format:
	ruff format src tests

grammar:
	cd tree-sitter-sysml && npm install && npm run generate

grammar-test:
	cd tree-sitter-sysml && npm test

clean:
	rm -rf build dist *.egg-info
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	rm -rf src/systree/__pycache__ tests/__pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
