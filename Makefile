.RECIPEPREFIX := >
.PHONY: lint test format pre-commit

lint:
>ruff check .
>mypy agent

test:
>pytest --cov=agent --cov-report=term-missing

format:
>ruff format .

pre-commit:
>pre-commit run --all-files
