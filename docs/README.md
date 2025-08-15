# Documentation

## User guide

The agent exposes a tiny HTTP server that serves incident and analysis
information.  When running locally it binds to `http://localhost:8000` and
offers two read‑only endpoints:

| Endpoint | Purpose |
| --- | --- |
| `/incidents` | List of incident bundle filenames. |
| `/analyses`  | List of analysis bundle filenames, newest first. |

### Choosing an LLM backend

The analysis runner supports either a deterministic mock model (useful for
development and tests) or the OpenAI API:

- **Mock LLM** – default, no network traffic.  Set `LLM_BACKEND=MOCK`.
- **OpenAI** – real calls to OpenAI's API.  Set `LLM_BACKEND=OPENAI` and provide
  `OPENAI_API_KEY` in the environment.

Additional environment variables control analysis behaviour:

| Variable | Description | Default |
| --- | --- | --- |
| `ANALYSIS_RATE_SECONDS` | How often the runner scans for new incidents. | `300` |
| `ANALYSIS_MAX_LINES` | Maximum lines read from each incident bundle. | `2000` |

### Sample flow (mock LLM)

1. Start the agent with `LLM_BACKEND=MOCK`.
2. Drop a JSONL incident file into `/data/incidents`.
3. After the next scan a corresponding analysis file appears under
   `/data/analyses` and `/analyses` will list it.
4. Use the example Lovelace card to visualise recent analyses in Home Assistant.

## Developer notes

- Set `LLM_BACKEND=MOCK` to run tests without network access.
- Real LLM tests are only executed when `OPENAI_API_KEY` is defined.
- Run `make pre-commit` before committing to execute linters and tests.
