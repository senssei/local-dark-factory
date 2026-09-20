# Implementation Plan: Sovereign Dark Factory (`plan.md`)

This plan defines the step-by-step development phases for **`06-dark-factory`** according to the AI-Native SDLC Playbook.

---

## Phase 1: Foundation & Domain Contracts
- [ ] Initialize repository environment: `pyproject.toml`, `requirements.txt`, `.gitignore`.
- [ ] Define immutable domain contracts in `dark_factory/domain/types.py`:
  - `TaskSpec`
  - `RunStatus`
  - `VerificationStep`
  - `StepExecution`
  - `EvidenceManifest`
- [ ] Define error hierarchy in `dark_factory/domain/errors.py`.
- [ ] Unit tests for domain contracts (`tests/test_domain.py`).

---

## Phase 2: Sandbox Execution Fabric
- [ ] Implement `Sandbox` base protocol in `dark_factory/sandbox/base.py`.
- [ ] Implement `GitWorktreeSandbox` in `dark_factory/sandbox/worktree.py`:
  - `git worktree add --detach`
  - Structured argv command execution with timeouts and sanitized environment
  - File reading/writing
  - `git diff` patch extraction
  - Idempotent cleanup (`git worktree remove --force`)
- [ ] Unit tests for `GitWorktreeSandbox` (`tests/test_sandbox.py`).

---

## Phase 3: Local Agent Harness (`05-local-coders` Bridge)
- [ ] Implement `AgentHarness` base class in `dark_factory/harness/base.py`.
- [ ] Implement `LocalCoderHarness` in `dark_factory/harness/local_coder.py`:
  - Connect to `local_coder` from `../05-local-coders`
  - Support model selection (`qwen2.5-coder:14b` for complex generation, `7b` / Prism for fast edits)
  - Telemetry capture (prompt tokens, completion tokens, latency)
  - Spend tracking ($0.00)
- [ ] Implement `OpenCodeHarness` in `dark_factory/harness/opencode.py` (headless CLI mode).
- [ ] Unit tests for harnesses (`tests/test_harness.py`).

---

## Phase 4: Deterministic Verification & Self-Healing
- [ ] Implement `VerificationRunner` in `dark_factory/verification/runner.py`:
  - Sequential gate execution
  - Non-zero exit code detection
  - Timeout enforcement
- [ ] Implement `SelfHealingLoop` in `dark_factory/verification/healing.py`:
  - Failure trace extraction (stdout/stderr + compiler errors)
  - Feedback prompt generation for the local model
  - Up to `N` repair iterations
- [ ] Unit tests for verification and healing (`tests/test_verification.py`).

---

## Phase 5: Durable Workflow Engine
- [ ] Implement SQLite schema and state manager in `dark_factory/orchestrator/engine.py`:
  - Atomic state transitions
  - Durable run ledger (`.factory/factory.db`)
  - Crash recovery & cleanup of dangling sandboxes
- [ ] Implement event publisher in `dark_factory/orchestrator/events.py` for live status streaming.
- [ ] Unit tests for state machine & recovery (`tests/test_orchestrator.py`).

---

## Phase 6: Evidence Locker & Storage
- [ ] Implement evidence writer in `dark_factory/storage/evidence.py`:
  - Write `diff.patch`
  - Write `manifest.json`
  - Write `transcript.log`
  - Write `telemetry.json`
- [ ] Unit tests for evidence storage (`tests/test_storage.py`).

---

## Phase 7: CLI & Human-in-the-Loop Operator Interface
- [ ] Implement CLI commands in `dark_factory/cli.py`:
  - `dark-factory doctor` (health check for Ollama, Prism, GPU, Git)
  - `dark-factory run` (task submission)
  - `dark-factory status [RUN_ID] [--watch]` (streaming status)
  - `dark-factory describe RUN_ID` (manifest, gate results, and patch)
  - `dark-factory review RUN_ID --approve [--branch <name>]` (apply and commit patch)
  - `dark-factory review RUN_ID --reject [--note <reason>]` (reject and archive)
- [ ] Create executable wrapper `bin/dark-factory`.
- [ ] Full end-to-end integration test (`tests/test_e2e.py`).
