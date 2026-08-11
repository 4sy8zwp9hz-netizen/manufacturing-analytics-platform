.PHONY: install data run test lint

install:
	python -m pip install -e ".[dev]"

data:
	python -m manufacturing_analytics.scripts.generate_data

run:
	uvicorn manufacturing_analytics.main:app --reload

test:
	pytest

lint:
	ruff check .

