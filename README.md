# HA LLM Ops Add-on (Alpha)

[![CI](https://github.com/lextiz/SolidHA/actions/workflows/ci.yml/badge.svg)](https://github.com/lextiz/SolidHA/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/lextiz/SolidHA/branch/main/graph/badge.svg)](https://codecov.io/gh/lextiz/SolidHA)

> **Goal:** A Home Assistant (HA) Supervisor add-on that continuously observes your HA system, performs LLM-driven root cause analysis (RCA) for instability, proposes safe fixes, and—optionally—executes guarded remediations after taking a backup.

## Quick Installation

[![Install Add-on](https://my.home-assistant.io/badges/supervisor_addon.svg)](https://my.home-assistant.io/redirect/supervisor_addon/?addon=ha_llm_ops&repository_url=https%3A%2F%2Fgithub.com%2Flextiz%2FSolidHA)

The add-on uses Home Assistant's ingress feature and adds a sidebar panel for viewing collected incidents and their suggested solutions.

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

  - Curates bundles: relevant logs, YAML snippets, entity snapshots, integration configs, versions.

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

  - Subscribes to key events, collects error traces, writes incident bundles to disk.

- **M0.3 – RCA Contract (No Calls)**

  - Define prompt contract & JSON schema; implement schema validators; write golden samples & tests.

- **M0.4 – Dev UX**

  - Minimal Lovelace panel/card or log tailer endpoint to visualize incidents.

----------

## Detailed Task Breakdown (Bite-Sized)

Below are ready-to-run bite-sized tasks for the autonomous agent. Each bullet is intended to be a single small PR.

# M2 — Guarded Executor

**Objective:** extend the analysis-only agent with the ability to apply **safe, allow-listed remediations** inside HA. All actions are gated by policy, backups, and dry-run verification.

---

## Scope

- ✅ Define **policy file**: what actions are allowed, when, and under what conditions.
- ✅ Add **executor framework**: guarded service calls via Supervisor/HA API.
- ✅ Add **backup + verify + rollback** for every execution.
- ✅ Expose new **endpoints** for action proposals and approvals.
- ✅ Extend UI with action approval flow.
- ❌ No new analysis features (analysis pipeline is stable from M1).
- ❌ No telemetry (still opt-in deferred).

---

## Definition of Done (M2)

- All executor actions strictly validated against policy file.
- Backups taken before every mutation; rollback path tested.
- Dry-run simulation supported and exposed in HTTP API.
- Integration tests show at least one remediation (e.g. restart an integration) working end-to-end in mock HA.
- Coverage threshold ≥ 85% for executor modules.
- UI shows pending proposals, requires explicit approval.

---

## Detailed Task Breakdown (Bite-Sized for Codex)

### M2.0 – Policy & contracts

1. **Task:** Add `agent/executor/policy.py`.
   - Define `Policy` pydantic model: `action_id`, `allowed`, `conditions`, `cooldown_s`.
   - Load from `policy.yaml` in add-on config dir.
   - Unit tests with valid/invalid policies.

2. **Task:** Add `agent/executor/contracts.py`.
   - Define `ActionProposal`, `ActionExecution`, `ExecutionResult`.
   - Ensure JSON schema export (similar to RCA).
   - Unit tests: schema validation, sample roundtrips.

### M2.1 – Executor framework

3. **Task:** Create `agent/executor/base.py`.
   - Abstract `Executor` class with `dry_run()` and `apply()` methods.

4. **Task:** Implement `agent/executor/supervisor.py`.
   - Use Supervisor API to call safe actions (e.g. restart add-on, reload integration).
   - Respect `Policy`.
   - Unit tests with mocked Supervisor HTTP.

5. **Task:** Add `agent/executor/manager.py`.
   - Map `ActionProposal` → correct executor.
   - Enforce policy lookup + cooldown.
   - Unit tests with fake executors and policies.

### M2.2 – Backup & rollback

6. **Task:** Add `agent/executor/backup.py`.
   - Trigger Supervisor snapshot API before execution.
   - Store snapshot ID in `ExecutionResult`.
   - Unit tests: simulate backup success/failure.

7. **Task:** Add rollback support in `manager.py`.
   - If execution fails, trigger snapshot restore.
   - Unit tests: forced failure path.

### M2.3 – HTTP endpoints

8. **Task:** Extend `agent/devux.py`.
   - Add POST `/actions/propose` → accept `ActionProposal`, run policy check, enqueue.
   - Add GET `/actions/pending` → list proposals awaiting approval.
   - Add POST `/actions/approve` → trigger execution with backup.
   - Unit tests: API contract, error cases.

### M2.4 – Integration & end-to-end

9. **Task:** Add E2E test with mock Supervisor API.
   - Proposal created, approved, executed → success path validated.

10. **Task:** Add Docker-based HA integration test.
   - Simulate unstable integration; LLM proposes “restart integration”; executor applies; verify status healthy.

### M2.5 – UI & docs

11. **Task:** Extend Lovelace card example.
   - Show pending actions with approve button.
   - Display execution result + rollback info.

12. **Task:** Update docs.
   - Policy file format.
   - Backup/rollback mechanism.
   - Example flows.

---

## Non-Goals for M2

- No advanced policies (time windows, user groups) — defer to M3.
- No telemetry.
- No external action marketplace.
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

Project icon by [Umeicon](https://www.flaticon.com/authors/umeicon).
