# Implementation Plan: Sovereign Dark Factory (`plan.md`)

This plan defines the step-by-step development phases for **`local-dark-factory`** according to the AI-Native SDLC Playbook.

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

## Phase 3: Local Agent Harness (Multi-Engine Router)
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

---

## Phase 8: Hardening & Security Audit Remediation

### 8.1 Critical Verification & State Safety (Priority 1)
- [x] **Reject Zero Verification Gates**: If no verification steps are detected or provided, abort run with an error unless an explicit `--no-verify` flag is set.
- [x] **Protect `AWAITING_REVIEW` in `recover()`**: Exclude `AWAITING_REVIEW` runs from being marked as `FAILED` during engine recovery; only target truly dead runs; run `git worktree prune`.
- [x] **Fix Self-Healing Prompt & Telemetry**:
  - Preserve original `initial_prompt` alongside the error trace in repair iterations.
  - Properly aggregate tokens and durations across all attempts instead of overwriting `last_telemetry`.
  - Emit live status callbacks for `VERIFYING` and `SELF_HEALING`.
  - Treat missing file blocks as a counted healing retry rather than immediate failure.

### 8.2 Gate Tamper Resistance (Priority 2)
- [x] **Immutable Verification Gates**:
  - Restore gate definitions from `base_rev` before running verification.
  - Detect when agent touches protected test files and revert them so verification evaluates true application code.
  - Reject/warn patches that tamper with verification gates unless `--allow-gate-edits` is explicitly set.

### 8.3 Safe Host Application in `review --approve` (Priority 3)
- [x] **Safe Patch Application**:
  - Validate patch with `git apply --check` before creating branches or applying.
  - Store and verify SHA256 digest of `diff.patch` recorded at verification time.
  - Stage only files explicitly modified by the patch (never indiscriminate `git add .`).
  - Graceful rejection if patch does not apply cleanly.

### 8.4 Execution & Environment Robustness
- [x] **Sanitize Process Environment**:
  - Scrub factory's `VIRTUAL_ENV`, `PYTHONPATH`, and git variables from child process environments.
- [x] **Robust CLI Parsing**:
  - Use `shlex.split` for `--test-cmd` arguments to preserve quotes and flags.
- [x] **Engine Fallback Clarity**:
  - Distinguish 404 (missing model) from connection errors in Ollama client before falling back to Prism.
- [x] **Exception Preservation**:
  - Save full traceback and evidence transcript when unhandled exceptions occur in `execute_run`.

### 8.5 Code Hygiene
- [x] Ensure SQLite connection closing with `contextlib.contextmanager` and auto-close.
- [x] Single atomic transaction for status transition + operator notes in `review_run`.

---

## Phase 9: Packaging & Release (GitHub & PyPI)

### 9.1 Package Build & Metadata Validation
- [x] Configure package metadata in `pyproject.toml` with `name = "local-dark-factory"`.
- [x] Create `dark_factory/__init__.py` with `__version__ = "0.1.0"`.
- [x] Validate wheel and source distribution build locally via `python3 -m build`.
- [x] Verify distribution packages with `twine check --strict dist/*`.
- [x] Add standard MIT `LICENSE` file.

### 9.2 GitHub CI & Automation Workflows
- [x] Add `.github/workflows/ci.yml`: automated matrix tests (`pytest`) and lint (`ruff`) on Python 3.11 and 3.12.
- [x] Add `.github/workflows/publish.yml`: automated release workflow with PyPI Trusted Publishing (OIDC).

### 9.3 GitHub Remote & Repository Setup
- [x] Create GitHub repository `senssei/local-dark-factory`.
- [x] Push local `main` branch and verify remote repository.
- [x] Tag and publish release `v0.1.0` with assets on GitHub.

### 9.4 PyPI Publication
- [ ] Configure PyPI Trusted Publisher for repository `senssei/local-dark-factory`.
- [ ] Publish initial release `v0.1.0` to PyPI.
- [ ] Verify clean installation in isolated environment: `pip install local-dark-factory`.

