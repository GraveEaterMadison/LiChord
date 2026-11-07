.PHONY: install test lint format run docker

install:
	python -m pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check .

format:
	ruff format .

run:
	lichord

docker:
	docker compose up --build -d
