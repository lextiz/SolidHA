# Home Assistant Add-On: Autofix problems with AI

## Disclaimer

This alpha version is not stable or reliable; it is in active development. Use at your own risk. If you have to sell your house to fund your OpenAI account I will accept no claims.

[![CI](https://github.com/lextiz/SolidHA/actions/workflows/ci.yml/badge.svg)](https://github.com/lextiz/SolidHA/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/lextiz/SolidHA/branch/main/graph/badge.svg)](https://codecov.io/gh/lextiz/SolidHA)

[![Install Add-on](https://my.home-assistant.io/badges/supervisor_addon.svg)](https://my.home-assistant.io/redirect/supervisor_addon/?addon=ha_llm_ops&repository_url=https%3A%2F%2Fgithub.com%2Flextiz%2FSolidHA)

> **Goal:** A Home Assistant (HA) Supervisor add-on that continuously observes your HA system, performs AI-driven root cause analysis for instability, proposes safe fixes, and optionally executes guarded remediations after taking a backup.

----------

## Motivation

Home Assistant is powerful, but complex stacks (integrations, add-ons, flaky devices, vendor APIs) often degrade reliability.

**This project** aims to add _operational intelligence_ to HA:

- Observe logs, events, and status signals.
- Triage problems with an LLM that has structured context.
- Output a clear RCA + stepwise plan.
- Safely apply allow‑listed remediations (opt‑in), with backup, verify, and rollback.

----------

## Roadmap

1. Autofix HA instabilities and have error-free logs
    1. M0 – Read-only Observer
    2. M1 – Analysis-Only Agent
    3. M2 – Guarded Executor
        - Allow‑listed actions (reload automations, restart integrations, reauth flow triggers, backups, core restart last-resort). Dry-run → approval → execute → verify.
    4. M3 – Policies & Scenario Tests
        - Policy file (what the agent may touch), quiet hours, mandatory verification tests, scenario suite in CI.
1. Ability to create and edit automations and other configurations according to user prompt, all safeguards and automatic validations above apply

----------

## Architecture (Target)

- **Add-on container (Alpine)** hosting the agent service.

- **Collectors**
  - HA WebSocket subscriptions: state changes, automation/script traces, errors.
  - Supervisor endpoints: add-on/core logs, health, updates, backups.
  - Repairs/Issue registry as first-class signal.
- **Context Packager**
  - Curates bundles: relevant logs, YAML snippets, entity snapshots, integration configs, versions.
- **RCA & Planner (LLM)**
  - Prompt contracts enforce JSON output: `root_cause`, `impact`, `confidence`, `candidate_actions[]`, `risk`, `tests[]`.
- **Guarded Executor (opt-in)**
  - Backup → apply allow‑listed tools → verify tests → rollback on fail.
- **Change Journal**
  - Persist problem + remediation outcomes for learning and few-shot examples.

----------

## Safety & Guardrails

- **Allow‑listed tools only.** No arbitrary service calls.
- **Dry‑run first.** Human or policy approval required for writes.
- **Backup-before-change.** Automated Supervisor backup for any mutating action.
- **Verification tests.** Post-conditions must pass; else rollback.
- **Redaction.** Secrets never leave the host; context bundles scrub tokens/PII.
- **Rate limits & cooldowns.** Avoid restart loops.

----------

## Getting Started (Developer)

> **Prereqs:** Docker, Git, and (for later milestones) a Home Assistant **Supervisor** environment for e2e tests.

1. **Clone**: `git clone https://github.com/<you>/ha-llm-ops && cd ha-llm-ops`
1. **Bootstrap**: `make bootstrap` (to be added in M0.0; installs pre-commit, sets up venv, etc.)
1. **Run unit tests**: `make test`
1. **Build add-on (local)**: `docker build -t ha-llm-ops:addon ./addons/ha-llm-ops`

----------

## Open Source: How to Contribute

- **Small PRs only** (≤ 200 LOC diff ideally). One atomic change per PR.
- **Branch naming**: `feat/<scope>-<slug>`, `fix/<scope>-<slug>`, `chore/...`
- **Commit format**: Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`).
- **CI is required**: All checks must pass (build, unit tests, lint, docker build, PR size guard).
- **Design changes**: Open a proposal in `docs/adr/` (use the ADR template) and link it in the PR.
- **Security**: No secrets in code; use `.env.example`. Report vulnerabilities privately via SECURITY.md.

----------

## Milestones

## Detailed Task Breakdown (Bite-Sized)

Below are ready-to-run bite-sized tasks for the autonomous agent. Each bullet is intended to be a single small PR.

### M2 — Guarded Executor

**Objective:** extend the analysis-only agent with the ability to apply **safe, allow-listed remediations** inside HA. All actions are gated by policy, backups, and dry-run verification.

----------

## Scope

- ✅ Define **policy file**: what actions are allowed, when, and under what conditions.
- ✅ Add **executor framework**: guarded service calls via Supervisor/HA API.
- ✅ Add **backup + verify + rollback** for every execution.
- ✅ Expose new **endpoints** for action proposals and approvals.
- ✅ Extend UI with action approval flow.
- ❌ No new analysis features (analysis pipeline is stable from M1).
- ❌ No telemetry (still opt-in deferred).

----------

## Definition of Done (M2)

- All executor actions strictly validated against policy file.
- Backups taken before every mutation; rollback path tested.
- Dry-run simulation supported and exposed in HTTP API.
- Integration tests show at least one remediation (e.g. restart an integration) working end-to-end in mock HA.
- Coverage threshold ≥ 85% for executor modules.
- UI shows pending proposals, requires explicit approval.

----------

## Detailed Task Breakdown

### M2.0 – Policy & contracts (status: done)

1. **Task:** Add `agent/executor/policy.py`.

    - Define `Policy` pydantic model: `action_id`, `allowed`, `conditions`, `cooldown_s`.
    - Load from `policy.yaml` in add-on config dir.
    - Unit tests with valid/invalid policies.

2. **Task:** Add `agent/executor/contracts.py`.

    - Define `ActionProposal`, `ActionExecution`, `ExecutionResult`.
    - Ensure JSON schema export (similar to RCA).
    - Unit tests: schema validation, sample roundtrips.

### M2.1 – Executor framework

1. **Task:** Create `agent/executor/base.py`.

    - Abstract `Executor` class with `dry_run()` and `apply()` methods.

2. **Task:** Implement `agent/executor/supervisor.py`.

    - Use Supervisor API to call safe actions (e.g. restart add-on, reload integration).
    - Respect `Policy`.
    - Unit tests with mocked Supervisor HTTP.

3. **Task:** Add `agent/executor/manager.py`.

    - Map `ActionProposal` → correct executor.
    - Enforce policy lookup + cooldown.
    - Unit tests with fake executors and policies.

### M2.2 – Backup & rollback

1. **Task:** Add `agent/executor/backup.py`.

    - Trigger Supervisor snapshot API before execution.
    - Store snapshot ID in `ExecutionResult`.
    - Unit tests: simulate backup success/failure.

2. **Task:** Add rollback support in `manager.py`.

    - If execution fails, trigger snapshot restore.
    - Unit tests: forced failure path.

### M2.3 – HTTP endpoints

1. **Task:** Extend `agent/devux.py`.

    - Add POST `/actions/propose` → accept `ActionProposal`, run policy check, enqueue.
    - Add GET `/actions/pending` → list proposals awaiting approval.
    - Add POST `/actions/approve` → trigger execution with backup.
    - Unit tests: API contract, error cases.

### M2.4 – Integration & end-to-end

1. **Task:** Add E2E test with mock Supervisor API.

    - Proposal created, approved, executed → success path validated.

2. **Task:** Add Docker-based HA integration test.

    - Simulate unstable integration; LLM proposes “restart integration”; executor applies; verify status healthy.

### M2.5 – UI & docs

1. **Task:** Extend Lovelace card example.

    - Show pending actions with approve button.
    - Display execution result + rollback info.

2. **Task:** Update docs.

    - Policy file format.
    - Backup/rollback mechanism.
    - Example flows.

----------

## Non-Goals for M2

- No advanced policies (time windows, user groups) — defer to M3.
- No telemetry.
- No external action marketplace.

----------

## License

Apache-2.0. See `LICENSE`.

----------

## Acknowledgments

This project builds on the Home Assistant ecosystem and the broader OSS community. Thank you to contributors and reviewers who keep the CI green and the scope sharp.

Project icon by [Umeicon](https://www.flaticon.com/authors/umeicon).
