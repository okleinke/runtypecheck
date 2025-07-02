.PHONY: test coverage lint format build

install:
	pip install -e .[dev]

test:
	pytest -q

coverage:
	pytest --cov=src/typecheck --cov-report=term-missing --cov-report=xml:coverage.xml --cov-fail-under=80

lint:
	ruff check src
	mypy src
	validate-pyproject pyproject.toml
	vulture src --min-confidence 80

format:
	isort src tests
	black src tests

build:
	python -m build
