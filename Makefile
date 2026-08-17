.PHONY: install data run test lint

install:
	python -m pip install -e ".[dev]"

data:
	python -m manufacturing_analytics.scripts.refresh_data

run:
	python -m manufacturing_analytics.main

test:
	python -m pytest

lint:
	python -m ruff check .
	python -m ruff format --check .
