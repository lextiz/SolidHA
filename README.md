# HA LLM Ops Add-on (Alpha)

[![CI](https://github.com/lextiz/SolidHA/actions/workflows/ci.yml/badge.svg)](https://github.com/lextiz/SolidHA/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/lextiz/SolidHA/branch/main/graph/badge.svg)](https://codecov.io/gh/lextiz/SolidHA)

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

### M1.0 – Analysis skeleton & contracts

1.  **Task:** Create `agent/analysis/__init__.py` and `agent/analysis/types.py`.
    
    -   Define typed structures for: `IncidentRef`, `ContextBundle`, `Prompt`, `RcaOutput` (alias of `RcaResult`).
        
    -   Add unit tests validating simple constructors and type hints (mypy strict).
        
2.  **Task:** Add `agent/analysis/storage.py`.
    
    -   Read incident files from `/data/incidents`.
        
    -   Map to `IncidentRef` (filename + time range).
        
    -   Unit tests with tmpdir fixtures (empty dir, multiple files, malformed line handling).
        
3.  **Task:** Add `agent/analysis/context.py`.
    
    -   Build `ContextBundle` from recent events around an incident (last N lines), deduplicate noisy repeats, enforce redaction.
        
    -   Unit tests: verify redaction, dedupe, size limits.
        

### M1.1 – Prompt builder

4.  **Task:** Add `agent/analysis/prompt_builder.py`.
    
    -   Deterministic prompt from `ContextBundle` + repo/version info + guardrails.
        
    -   Export prompt as **pure text** plus a **JSON schema section** (copied from `RcaResult.model_json_schema()`).
        
5.  **Task:** Golden tests for prompt builder.
    
    -   Create `tests/golden/prompt_input.json` and `tests/golden/prompt_output.txt`.
        
    -   Snapshot test ensuring prompt text matches exactly; add an allowlisted small “update snapshot” script.
        

### M1.2 – LLM adapters (read-only)

6.  **Task:** Create `agent/analysis/llm/base.py`.
    
    -   Define `LLM` protocol: `generate(prompt: str, *, timeout: float) -> str`.
        
7.  **Task:** Add `agent/analysis/llm/mock.py`.
    
    -   Deterministic stub returning a canned, valid `RcaResult` JSON for tests.
        
8.  **Task:** Add `agent/analysis/llm/openai.py` (adapter only).
    
    -   Read `OPENAI_API_KEY` from env.
        
    -   Compose JSON-only system prompt: “Respond with **only** valid JSON per schema below; no prose.”
        
    -   Parse/return raw string (no model validation here).
        
    -   Unit tests: environment handling + timeouts (use mock HTTP).
        
9.  **Task:** Add `agent/analysis/parse.py`.
    
    -   Strict parsing: JSON load → pydantic `RcaResult`.
        
    -   Defensive errors surfaced with actionable messages.
        
    -   Unit tests with valid/invalid payloads.
        

### M1.3 – Analysis runner & endpoints

10.  **Task:** Add `agent/analysis/runner.py`.
    
    -   Scheduler: scan for new incident files; rate-limit; enqueue to analyze; backoff on failures.
        
    -   Pluggable LLM (`MOCK` default, `OPENAI` if env present).
        
    -   Persist analyses as JSONL in `/data/analyses/analyses_*.jsonl` (size-rotated).
        
    -   Unit tests: queueing, rate-limit, rotation.
        
11.  **Task:** Extend HTTP server in `agent/devux.py`.
    
    -   Add GET `/analyses` → returns latest analyses (filenames or inline last N).
        
    -   Unit tests for handler (404, empty, non-empty).
        
12.  **Task:** Wire the runner in `addons/ha-llm-ops/agent/__main__.py`.
    
    -   Start analysis runner alongside observer and HTTP server.
        
    -   Config via env: `ANALYSIS_RATE_SECONDS`, `ANALYSIS_MAX_LINES`, `LLM_BACKEND`.
        
    -   Unit test: start/stop with mock LLM; verify runner called.
        

### M1.4 – End-to-end & integration

13.  **Task:** Add E2E test with **mock LLM** (no network).
    
    -   Create a synthetic incident file; run runner once; assert a valid `RcaResult` stored; verify `/analyses` lists it.
        
14.  **Task:** Extend Docker-based HA integration test.
    
    -   After generating at least one incident, run the analysis once with mock LLM; assert a persisted analysis appears.
        
15.  **Task:** Coverage & CI
    
    -   Raise coverage threshold to 85% for analysis modules.
        
    -   Ensure CI skips real LLM tests unless `OPENAI_API_KEY` is set (matrix job optional).
        

### M1.5 – Minimal UI

16.  **Task:** Add example Lovelace card YAML (docs/):
    
    -   Panel listing `/analyses` newest-first; clicking an item shows parsed `RcaResult`.
        
17.  **Task:** Documentation: user & dev guides.
    
    -   How to enable mock vs. real LLM, env vars, expected endpoints, sample flows.
        

----------

## Non-Goals for M1

-   No mutating actions (service calls, restarts, reauth)
    
-   No policy file or executor (M2)
    
-   No telemetry collection

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
