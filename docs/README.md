# Documentation

## User guide

The agent exposes a tiny HTTP server that serves problem information. When running locally it binds to `http://localhost:8000` and offers:

| Endpoint | Purpose |
| --- | --- |
| `/` | List of problem log filenames. |
| `/problems/<name>` | Contents of a problem log. |

### Analysis settings

The agent analyses relevant events as they happen. Environment variables control rate limiting and context size:

| Variable | Description | Default |
| --- | --- | --- |
| `ANALYSIS_RATE_SECONDS` | Minimum seconds between analyses. | `300` |
| `ANALYSIS_MAX_LINES` | Maximum lines of context sent to the LLM. | `2000` |

When `OPENAI_API_KEY` is defined, the agent sends prompts to OpenAI. Otherwise a deterministic mock model is used.
