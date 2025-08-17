# AGENTS

- **KISS**
- Make sure the change keeps the architecture and module structure reasonable, if necessary refactor and deduplicate.
- No migration support required for breaking changes: keep the code simple, if there are breaking changes mention this and we will ask users to delete the data.
- No secrets in code.
- All new code has to be completely covered by tests that make sense. Update tests with every behavior change, if fixing a bug add a regression test.
- Run `ruff check . --fix && ruff format . && mdformat . && mypy --install-types --non-interactive .` to validate code changes before submitting.
- Bump version in addons/ha-llm-ops/config.yaml.
