.RECIPEPREFIX := >
.PHONY: lint test format pre-commit

lint:
>ruff check .
>mypy agent

test:
>pytest --cov=agent --cov=addons/ha-llm-ops/agent --cov-report=term-missing --cov-fail-under=100

format:
>ruff format .

pre-commit:
>pre-commit run --all-files
