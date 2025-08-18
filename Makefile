.RECIPEPREFIX := >
.PHONY: lint test format pre-commit

lint:
>ruff check .
>mypy addons/ha-llm-ops/agent

test:
>pytest --cov=agent --cov-report=term-missing --cov-fail-under=100

format:
>ruff format .

pre-commit:
>pre-commit run --all-files
