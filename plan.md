# Implementation Plan: Sovereign Dark Factory (`plan.md`)

This plan defines the step-by-step development phases for **`06-dark-factory`** according to the AI-Native SDLC Playbook.

---

## Phase 1: Foundation & Domain Contracts
- [x] Initialize repository environment: `pyproject.toml`, `requirements.txt`, `.gitignore`.
- [x] Define immutable domain contracts in `dark_factory/domain/types.py`:
  - `TaskSpec`
  - `RunStatus`
  - `VerificationStep`
  - `StepExecution`
  - `EvidenceManifest`
- [x] Define error hierarchy in `dark_factory/domain/errors.py`.
- [x] Unit tests for domain contracts (`tests/test_domain.py`).

---

## Phase 2: Sandbox Execution Fabric
- [x] Implement `Sandbox` base protocol in `dark_factory/sandbox/base.py`.
- [x] Implement `GitWorktreeSandbox` in `dark_factory/sandbox/worktree.py`:
  - `git worktree add --detach`
  - Structured argv command execution with timeouts and sanitized environment
  - File reading/writing
  - `git diff` patch extraction
  - Idempotent cleanup (`git worktree remove --force`)
- [x] Unit tests for `GitWorktreeSandbox` (`tests/test_sandbox.py`).

---

## Phase 3: Local Agent Harness (`05-local-coders` Bridge)
- [x] Implement `AgentHarness` base class in `dark_factory/harness/base.py`.
- [x] Implement `LocalCoderHarness` in `dark_factory/harness/local_coder.py`:
  - Connect to local Ollama (`http://localhost:11434`) and Prism (`http://127.0.0.1:5272/v1`)
  - Support model selection (`qwen2.5-coder:14b` for complex generation, `7b` / Prism for fast edits)
  - Telemetry capture (prompt tokens, completion tokens, latency, tokens/sec)
  - Spend tracking ($0.00 cloud token cost)
- [x] Unit tests for harnesses (`tests/test_harness.py`).

---

## Phase 4: Deterministic Verification & Self-Healing
- [x] Implement `VerificationRunner` in `dark_factory/verification/runner.py`:
  - Sequential gate execution
  - Non-zero exit code detection
  - Timeout enforcement
- [x] Implement `SelfHealingLoop` in `dark_factory/verification/healing.py`:
  - Failure trace extraction (stdout/stderr + compiler errors)
  - Feedback prompt generation for the local model
  - Up to `N` repair iterations
- [x] Unit tests for verification and healing (`tests/test_verification.py`).

---

## Phase 5: Durable Workflow Engine (Option C Architecture)
- [x] Implement stateless workflow activities in `dark_factory/orchestrator/activities.py`:
  - `activity_create_sandbox`
  - `activity_execute_task_and_verify`
  - `activity_preserve_evidence`
  - `activity_apply_patch`
  - `activity_cleanup_sandbox`
- [x] Implement SQLite schema and state manager in `dark_factory/orchestrator/engine.py`:
  - Atomic state transitions (`WAL` mode)
  - Durable run ledger (`.factory/factory.db`)
  - Crash recovery & cleanup of dangling sandboxes
- [x] Unit tests for state machine & recovery (`tests/test_orchestrator.py`).

---

## Phase 6: Evidence Locker & Storage
- [x] Implement evidence writer in `dark_factory/storage/evidence.py`:
  - Write `diff.patch`
  - Write `manifest.json`
  - Write `transcript.log`
  - Write `telemetry.json`
- [x] Unit tests for evidence storage (`tests/test_storage.py`).

---

## Phase 7: CLI & Human-in-the-Loop Operator Interface
- [x] Implement CLI commands in `dark_factory/cli.py`:
  - `dark-factory doctor` (health check for Ollama, Prism, GPU, Git)
  - `dark-factory run` (task submission with live transition streaming)
  - `dark-factory list` (runs list)
  - `dark-factory describe RUN_ID` (manifest, gate results, and patch)
  - `dark-factory review RUN_ID --approve [--branch <name>]` (apply and commit patch)
  - `dark-factory review RUN_ID --reject [--note <reason>]` (reject and archive)
  - `dark-factory recover` (recover crashed runs and prune dead sandboxes)
- [x] Create executable wrapper `bin/dark-factory`.
- [x] Full end-to-end integration test (`tests/test_e2e.py`).
- [x] Verification profiles in `profiles/default.toml` and `profiles/python.toml`.
