# HA LLM Ops Add-on (Alpha)

[![CI](https://github.com/YourOrg/SolidHA/actions/workflows/ci.yml/badge.svg)](https://github.com/YourOrg/SolidHA/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/YourOrg/SolidHA/branch/main/graph/badge.svg)](https://codecov.io/gh/YourOrg/SolidHA)

> **Goal:** A Home Assistant (HA) Supervisor add-on that continuously observes your HA system, performs LLM-driven root cause analysis (RCA) for instability, proposes safe fixes, and—optionally—executes guarded remediations after taking a backup.

----------

## Motivation

Home Assistant is powerful, but complex stacks (integrations, add-ons, flaky devices, vendor APIs) often degrade reliability. Typical pain points:

- Random integration / device failures, stuck config entries, and migrations.

- Manual restarts (integration, core, or host) to unstick things.

- Silent automation failures and brittle edge-cases.

- Vendor flows that require user re-authentication or ToS confirmation.

**This project** aims to add _operational intelligence_ to HA:

- Observe logs, events, and status signals.

- Triage incidents with an LLM that has structured context.

- Output a clear RCA + stepwise plan.

- Safely apply allow‑listed remediations (opt‑in), with backup, verify, and rollback.

----------

## High-Level Plan

1. **M0 – Read-only Observer (Foundations)**

    - Add-on scaffold, observability, minimal UI, CI/testability, docs.

    - LLM proposes fixes but **does not** change HA.

2. **M1 – Analysis-Only Agent**

    - Strict JSON schema outputs (RCA + plan + tests). No writes.

3. **M2 – Guarded Executor**

    - Allow‑listed actions (reload automations, restart integrations, reauth flow triggers, backups, core restart last-resort). Dry-run → approval → execute → verify.

4. **M3 – Policies & Scenario Tests**

    - Policy file (what the agent may touch), quiet hours, mandatory verification tests, scenario suite in CI.

----------

## Architecture (Target)

- **Add-on container (Alpine)** hosting the agent service.

- **Collectors**

  - HA WebSocket subscriptions: state changes, automation/script traces, errors.

  - Supervisor endpoints: add-on/core logs, health, updates, backups.

  - Repairs/Issue registry as first-class signal.

- **Context Packager**

  - Curates redacted bundles: relevant logs, YAML snippets, entity snapshots, integration configs, versions.

- **RCA & Planner (LLM)**

  - Prompt contracts enforce JSON output: `root_cause`, `impact`, `confidence`, `candidate_actions[]`, `risk`, `tests[]`.

- **Guarded Executor (opt-in)**

  - Backup → apply allow‑listed tools → verify tests → rollback on fail.

- **Change Journal**

  - Persist incident + remediation outcomes for learning and few-shot examples.

----------

## Safety & Guardrails

- **Allow‑listed tools only.** No arbitrary service calls.

- **Dry‑run first.** Human or policy approval required for writes.

- **Backup-before-change.** Automated Supervisor backup for any mutating action.

- **Verification tests.** Post-conditions must pass; else rollback.

- **Redaction.** Secrets never leave the host; context bundles scrub tokens/PII.

- **Rate limits & cooldowns.** Avoid restart loops.

----------

## Repository Layout (proposed)

```text
ha-llm-ops/
  addons/ha-llm-ops/        # HA add-on (Dockerfile, config.yaml, run scripts)
  agent/                    # Agent service (Python) & LLM adapters
  agent/contracts/          # JSON schemas for prompts & outputs
  agent/tools/              # Allow-listed actions (M2+)
  tests/                    # Unit & integration tests (incl. scenario seeds)
  docs/                     # Design notes, ADRs, threat model
  .github/workflows/        # CI pipelines
  CONTRIBUTING.md
  CODE_OF_CONDUCT.md
  LICENSE
  README.md
```

----------

## Getting Started (Developer)

> **Prereqs:** Docker, Git, and (for later milestones) a Home Assistant **Supervisor** environment for e2e tests.

1. **Clone**: `git clone https://github.com/<you>/ha-llm-ops && cd ha-llm-ops`

2. **Bootstrap**: `make bootstrap` (to be added in M0.0; installs pre-commit, sets up venv, etc.)

3. **Run unit tests**: `make test`

4. **Build add-on (local)**: `docker build -t ha-llm-ops:addon ./addons/ha-llm-ops`

----------

## Open Source: How to Contribute

- **Small PRs only** (≤ 200 LOC diff ideally). One atomic change per PR.

- **Branch naming**: `feat/<scope>-<slug>`, `fix/<scope>-<slug>`, `chore/...`

- **Commit format**: Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`).

- **CI is required**: All checks must pass (build, unit tests, lint, docker build, PR size guard).

- **Design changes**: Open a proposal in `docs/adr/` (use the ADR template) and link it in the PR.

- **Security**: No secrets in code; use `.env.example`. Report vulnerabilities privately via SECURITY.md.

----------

## Autonomous Agent Contribution Protocol (Codex/ChatGPT)

**Intent:** Allow a ChatGPT/Codex agent to progress the repo in bite-sized steps under CI.

### Hard Rules

1. **Never push to** `**main**`**.** Create a branch & open a PR.

2. **Keep PRs small** and self-contained.

3. **Update tests** (or add) with every behavior change.

4. **No network secrets** in tests; use mocks or fixtures.

5. **Follow checklists** in PR description and keep them all checked.

### PR Template Checklist (autofilled by CI)

**Task Format for the Agent** Provide tasks as plain text bullets or numbered steps. The agent should:

- Execute them in order.

- If blocked, open a follow-up PR with a **smaller** step that unblocks.

- Prefer adding failing tests first, then code until green.

----------

## Milestones

### M0 — Read-only Observer Foundations

**Outcome:** A built, tested, documented repository with add-on scaffolding and log/event collection in place. LLM stubs only.

- **M0.0 – Testability & CI (hello-world level)**

  - Minimal repo bootstrap, container builds, and unit-test scaffolding.

  - CI runs on PRs and `main` merges.

  - Artifacts: docker images build; basic pytest “hello world” passes; linters run.

- **M0.1 – Add-on Skeleton**

  - `addons/ha-llm-ops/` with `config.yaml`, `Dockerfile`, entrypoint.

  - Start/stop lifecycle verified, logs visible, healthcheck.

- **M0.2 – Observability (Read-only)**

  - Agent connects to HA WebSocket (configurable URL/token for dev vs Supervisor token in add-on).

  - Subscribes to key events, collects error traces, writes redacted incident bundles to disk.

- **M0.3 – RCA Contract (No Calls)**

  - Define prompt contract & JSON schema; implement schema validators; write golden samples & tests.

- **M0.4 – Dev UX**

  - Minimal Lovelace panel/card or log tailer endpoint to visualize incidents.

----------

## Detailed Task Breakdown (Bite-Sized)

Below are ready-to-run bite-sized tasks for the autonomous agent. Each bullet is intended to be a single small PR.

### M0.0 – Testability & CI

1. **Task:** Initialize repo scaffolding.

    - Add `README.md` (this file), `LICENSE` (Apache-2.0), `.gitignore` for Python/Docker/Node, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `SECURITY.md` (with disclosure email placeholder).

    - Add `.editorconfig` and basic `.gitattributes`.

2. **Task:** Add Python project skeleton for `agent/`.

    - Create `agent/pyproject.toml` using `uv` or `poetry` (fallback: `pip-tools`).

    - Dependencies (dev): `pytest`, `ruff`, `mypy`, `pytest-cov`; (runtime for later) `websockets`, `httpx`, `pydantic`.

    - Add `agent/src/ha_llm_ops/__init__.py` and `agent/tests/test_sanity.py` with a hello-world test.

3. **Task:** Add `Makefile` for common dev commands.

    - Targets: `bootstrap`, `fmt`, `lint`, `typecheck`, `test`, `build-addon`, `clean`.

4. **Task:** Configure linters & types.

    - Add `ruff.toml` (enable common rules), `mypy.ini` (strict-ish), and `pyproject` tool configs.

5. **Task:** Add Dockerfiles for CI.

    - `./Dockerfile.ci` that installs python, dependencies, and runs tests.

    - Ensure deterministic builds (pin base image tag).

6. **Task:** GitHub Actions – CI pipeline.

    - Workflow `.github/workflows/ci.yml` with jobs:

        - **lint**: ruff + mypy.

        - **test**: run pytest with coverage and upload report artifact.

        - **docker**: build `Dockerfile.ci` and also build add-on image (stub) to validate Docker builds.

    - Triggers: on PRs and pushes to `main`.

7. **Task:** Add PR Template & labels.

    - `.github/pull_request_template.md` with checklist from this README.

    - Default labels: `area/ci`, `area/docs`, `good first issue`.

8. **Task:** Pre-commit hooks.

    - Configure `.pre-commit-config.yaml` for ruff, trailing-whitespace, end-of-file-fixer, detect-private-keys.

9. **Task:** Minimal add-on stub for build validation.

    - Create `addons/ha-llm-ops/config.yaml` with placeholder metadata and schema.

    - Create `addons/ha-llm-ops/Dockerfile` that just prints hello and exits (until M0.1).

10. **Task:** Status badge wiring.

    - Add CI status badge and codecov placeholder to README.

11. **Task:** Documentation checks.

    - Add a doc linter job (markdownlint) via `node` action or a container.

12. **Task:** Repository governance.

    - Enable branch protection for `main` (required checks, linear history, signed commits optional).

> **Definition of Done (M0.0):** CI is green; `make test` and `docker build` succeed locally; PR template enforces small, tested changes; minimal add-on image builds in CI.

### M0.1 – Add-on Skeleton

1. **Task:** Implement real add-on entrypoint script (`/run.sh`) that starts the agent with a no-op loop.

2. **Task:** Add healthcheck and logs to stdout; verify Supervisor expectations.

3. **Task:** Parameterize config options in `config.yaml` (log level, buffer size, incident dir).

### M0.2 – Observability (Read-only)

1. **Task:** Implement WebSocket client with reconnect/backoff.

2. **Task:** Subscribe to error/trace events and write rotating JSONL to `/data/incidents/`.

3. **Task:** Add redaction utility (token patterns, secrets.yaml keys).

4. **Task:** Add unit tests with fixtures for typical HA events and error samples.

### M0.3 – RCA Contract

1. **Task:** Define `contracts/rca_v1.json` schema (pydantic models + JSON schema export).

2. **Task:** Add schema validator + golden test vectors.

3. **Task:** Implement prompt builder (no API calls yet) and snapshot tests of rendered prompts.

### M0.4 – Dev UX

1. **Task:** Expose a minimal HTTP endpoint from the agent to list incident bundles.

2. **Task:** Provide an example Lovelace card YAML that polls the endpoint.

----------

## Environment Variables (planned)

- `HA_WS_URL` – HA WebSocket URL (dev mode only; add-on will auto-use Supervisor token/URL).

- `SUPERVISOR_TOKEN` – injected by HA when running as an add-on (do not set manually).

- `INCIDENT_DIR` – default `/data/incidents`.

- `LOG_LEVEL` – default `INFO`.

----------

## License

Apache-2.0. See `LICENSE`.

----------

## Roadmap at a Glance

- M0 foundations ✅ (you are here)

- M1 strict analysis (no writes)

- M2 guarded executor (backup-first)

- M3 policies + scenario tests + docs

----------

## Acknowledgments

This project builds on the Home Assistant ecosystem and the broader OSS community. Thank you to contributors and reviewers who keep the CI green and the scope sharp.
