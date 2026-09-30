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
> **ON HOLD (operator decision):** no release for now. Resume after Phase 10 review; first PyPI release will carry the Phase 10 fixes.

- [ ] Configure PyPI Trusted Publisher for repository `senssei/local-dark-factory`.
- [ ] Publish initial release `v0.1.0` to PyPI.
- [ ] Verify clean installation in isolated environment: `pip install local-dark-factory`.

---

## Phase 10: Post-Release Audit Remediation

**Status:** implemented, verified, and **committed** (2026-09-29: `7ff5abb` eval+dashboard packages, `19f035b` everything else — not pushed to any remote). 145 tests, `ruff check`, `ruff format --check`, `mkdocs build --strict` all green; a full run including every `local_engine` real-model test passes against the operator's real Ollama. Changes are recorded under `[Unreleased]` in `CHANGELOG.md`. 10.6, 10.8, 10.9, 10.10, 10.11, 10.12, 10.13, 10.14, and 12 (eval harness + read-only dashboard) are all fully closed; remaining pre-release work is 10.7 (doc/ops alignment, non-blocking, now 9 items — including a real `_build_context` context-bloat bug found via dogfooding, documented not fixed per operator decision) plus the operator's explicit go-ahead to release.

Source: code audit of `main` @ `73fb622`. Every fix ships with a regression test written first (red → green).
Release is **on hold** (operator decision): Phase 9.4 (PyPI) and the version bump stay open until the operator schedules a release; the target version is decided then (`0.1.1` was the working assumption).

### 10.1 Verification Integrity (Priority 1)
- [x] **Fence-safe file block parser** (`harness/local_coder.py`): a `` ```file:`` block must not be truncated by inner
  code fences (e.g. `README.md`, docstrings). Parse with fence-length matching / line-anchored closing fence.
- [x] **Fix `lstrip("./")` gate-path bug** (`verification/runner.py`): use `removeprefix`, so `.github/...` and `.venv/...`
  are not mangled into `github/...` / `venv/...`.
- [x] **Protect test-runner configuration** by default: `pyproject.toml`, `setup.cfg`, `conftest.py` (any depth),
  `.coveragerc`, `sitecustomize.py`, `usercustomize.py` in `detect_default_gate_paths()`.
- [x] **Block sandbox writes to `.git*`** (`sandbox/worktree.py`): `write_file` must reject `.git` / `.git/**`
  (worktree `gitdir:` pointer hijack).
- [x] **No-op runs are not successes**: a passing run with an empty diff ends `FAILED` (reason `empty_patch`), never
  `AWAITING_REVIEW`.

### 10.2 Patch Extraction & Application (Priority 2)
- [x] **Deterministic `get_diff`**: `--no-color --no-ext-diff --src-prefix=a/ --dst-prefix=b/ --binary`; check
  `git diff` / `git add -N` exit codes and raise `SandboxError` instead of returning a silent empty patch.
- [x] **Robust `parse_patch_files`**: handle paths with spaces and quoted (C-escaped) paths by parsing the `diff --git a/X b/X` header;
  `get_diff` passes `--no-renames` so every file appears once; staging uses `--literal-pathspecs`.
- [x] **Atomic `activity_apply_patch`**: on failure after `checkout -b`, return to the original branch and delete the
  new branch; wrap `CalledProcessError` in `DarkFactoryError`; refuse to apply on a dirty tree touching the same files.

### 10.3 Lifecycle & Durability (Priority 3)
- [x] **Run deadline**: enforce `TaskSpec.timeout_minutes` across harness + verification; terminal status `TIMED_OUT`.
- [x] **Cancellation**: `KeyboardInterrupt` / `SystemExit` → status `CANCELLED`, sandbox cleaned, evidence saved.
- [x] **Evidence before status**: persist `diff.patch` + `manifest.json` *before* the DB transition to `AWAITING_REVIEW`,
  so a crash can never leave an evidence-less review run.
- [ ] Remove dead `TaskSpec` fields (`agent`, `metadata`) or wire them up; drop the redundant `.git` check in
  `GitWorktreeSandbox.create`. **Deferred:** the fields are public API of the published `0.1.0`; decide at `0.2.0`.

### 10.4 Release Hygiene
- [x] Update `spec.md` (§2, §3.1, §3.2, §3.3, §3.4) and `CHANGELOG.md` (`[Unreleased]`; renamed to `[0.1.1]` at release).
- [x] CI: add `ruff format --check` and `mkdocs build --strict` jobs.
- [ ] **On hold:** bump version (`pyproject.toml`, `dark_factory/__init__.py`), rename `[Unreleased]` in `CHANGELOG.md`, tag. Operator gate; do not start without an explicit go.

### 10.5 Backlog (not in the next release)
- [ ] Record `patch_sha256` in the SQLite `events` table and verify it unconditionally in `review_run`
  (the manifest lives next to the patch, so it is not an independent integrity anchor).
- [ ] Stronger isolation for verification steps (rootless container / `bwrap`, no network): document the current
  worktree-only limitation in `spec.md` until then.
- [ ] Raise coverage on `harness/local_coder.py` (`_call_model` with mocked `requests`) and `cli.py` (`run`, `describe`,
  `review`) from ~55% to ≥85%.
- [ ] Default gate discovery in `cmd_run` should inspect `--base-rev`, not the working tree.

---

### 10.6 Post-Implementation Adversarial Audit — Code Defects

**Status: done (2026-09-28).** Source: adversarial review of the uncommitted `git diff` (≈968 / -145 LOC,
20 files). Items below were **introduced-or-revealed-by** the Phase 10 changes and shipped with the
`0.1.1` cut alongside 10.1–10.4. Every item shipped with a regression test written first (red → green).

- [x] **Hard-bound run deadline** (`verification/runner.py:115-122`). The clamp
  `int(deadline - time.monotonic())` truncates toward zero and is then floored by `max(1, ...)`; the next gate
  still gets **≥1 second** even when the deadline has already passed. Before invoking the next `sandbox.execute`,
  short-circuit with `if deadline is not None and time.monotonic() >= deadline: return VerificationOutcome(passed=False, ..., failed_step=StepExecution(step_id="deadline", exit_code=124, ...))` (or a dedicated `VerificationTimeoutError`). **Test:** a step past deadline returns immediately, with `exit_code == 124` and no subprocess invocation.

- [x] **`CANCELLED` preserves `diff.patch`** (`orchestrator/engine.py`). The
  `except (KeyboardInterrupt, SystemExit)` branch now routes through `activity_preserve_evidence` with
  `_best_effort_diff(sandbox)` (falling back to a plain `locker.save_run` only when the sandbox was never
  created), so a cancelled run keeps the same evidence shape as any other terminal state. **Test:**
  `test_cancelled_run_preserves_partial_diff`.

- [x] **Reconciliation covers the review window** (`orchestrator/engine.py`, `_reconcile_review_completeness`
  + `recover()`). `recover()` now also scans rows already marked `APPROVED`/`REJECTED` and flags any whose
  on-disk manifest never caught up (crash between `transition_status` and the final `locker.save_run` in
  `review_run`) as `FAILED` with an explanatory note — the patch may already be committed, so the safe move
  is to surface the inconsistency rather than re-derive or re-apply it. **Tests:**
  `test_recover_flags_approved_transition_that_never_completed`,
  `test_recover_leaves_genuinely_completed_approval_alone`.

- [x] **Derive terminal-status list from the `RunStatus` enum** (`orchestrator/engine.py`). Replaced the
  hardcoded `WHERE status NOT IN (...)` string list with a module-level
  `_NON_ORPHAN_STATUSES = {s.value for s in RunStatus if s.is_terminal} | {AWAITING_REVIEW}`, used by
  `recover()` via a parameterized query. **Test:** `test_non_orphan_statuses_derived_from_run_status_enum`.

- [x] **Locale-safe git stderr/stdout** (`orchestrator/activities.py:_git`,
  `sandbox/worktree.py` — all `text=True` subprocess/Popen call sites). Added `errors="replace"` throughout
  so a non-ASCII path outside the host locale decodes instead of raising `UnicodeDecodeError` mid-operation.
  **Tests:** `test_git_helper_subprocess_calls_are_locale_safe`, `test_worktree_git_calls_are_locale_safe`.

- [x] **Tighten `restore_paths` pathspec handling** (`sandbox/base.py:Sandbox.restore_paths`). Documented
  the contract: implementations must honor `:(glob)` pathspec magic, not just literal filesystem paths, or
  gate protection silently stops covering nested files (`GitWorktreeSandbox` already does, via passing the
  pathspec straight through to `git diff`/`git checkout`). **Test (doc-level):**
  `test_sandbox_restore_paths_contract_documents_glob_pathspecs`.

---

### 10.7 Post-Implementation Adversarial Audit — Documentation & Operations Alignment

**Status:** implemented and gate-green 2026-09-30 (150 tests, ruff, mkdocs --strict, changelog); uncommitted; only the `_build_context` item below remains open (documented, not fixed, per operator decision). Review: independent subagent, 10 findings (7 fixed: 1-7; 3 not defects or out of scope: 8-10); fixes verified by tests and the gate only, not re-reviewed. Decisions 2026-09-30 (Foundry: remove; Docker: non-goal; Temporal: seam wording; <100ms: drop). Plan
approved by the operator, 2026-09-30 (including the `intent.md` edits). **Invariant:** `docs/sdlc/{intent,spec,claude,agents}.md` are byte-identical
copies of the root files and must be edited together. One new test module, `tests/test_docs_alignment.py`, guards the
grep-able decisions (red first); the remaining items are prose proven by `mkdocs build --strict`.

**Source:** adversarial review of `docs/*.md`, `intent.md`, `spec.md`, `README.md` against
`dark_factory/` + `pyproject.toml`. Items below are **doc / operational** drift; they do **not** block
`0.1.1` but should land before the next release that touches the affected surfaces.

- [x] **Foundry Local: remove references** (decided by the operator 2026-09-30: docs-only). Harness stays Ollama → Prism.
  Files: `spec.md:164`, `docs/local-inference.md:25`, `README.md:46`, `CLAUDE.md:74,76`, `AGENTS.md`,
  `dark_factory/harness/local_coder.py:20`, `dark_factory/domain/types.py:97`, `dark_factory/domain/errors.py:25`
  (docstrings/messages only), plus the `docs/sdlc/{spec,claude,agents}.md` copies. `foundry-coder` stays an operator skill,
  not a factory backend. **Test:** `tests/test_docs_alignment.py::test_no_foundry_backend_references`.

- [x] **DockerSandbox: move to Non-Goals** (decided 2026-09-30). **Edits `intent.md` (an invariant): needs explicit
  operator approval of the new text.** Files: `intent.md:39`, `spec.md:151`, `docs/architecture.md:60` and the
  `docs/sdlc/{intent,spec}.md` copies. **Test:** `tests/test_docs_alignment.py::test_docker_sandbox_is_non_goal`.

- [x] **Temporal Option C: reword as a seam** (decided 2026-09-30). Text: "Option C is a forward-looking seam; no
  Temporal worker is registered in this release." Files: `docs/architecture.md:3`,
  `dark_factory/orchestrator/activities.py:1-4` (docstring), `intent.md:42` (optional adapter wording, same approval as
  the DockerSandbox `intent.md` edit) and `docs/sdlc/intent.md`. **Test:** `tests/test_docs_alignment.py::test_temporal_is_described_as_seam`.

- [x] **Expose `--timeout-minutes`, `--storage-dir`, `--ollama-url`, `--prism-url` on `dark-factory run`**
  (done as part of 10.8, which needed `--storage-dir`/`--ollama-url` to make the CLI e2e test
  deterministic). `list`/`describe`/`review`/`recover` also gained `--storage-dir` for consistency.
  `--harness` and `--protected-paths` remain tracked in Phase 11 (protocol-level decisions). **Test:**
  `test_cli_run_respects_timeout_minutes_and_storage_dir`.

- [x] **Refresh `docs/cli.md:118-122` (`recover`)** (verify against `_reconcile_orphan` in `orchestrator/engine.py`; proof is
  `mkdocs build --strict`, no unit test) so the description matches `_reconcile_orphan`: it
  now adopts evidence-backed final statuses; only runs whose manifest is unreadable are escalated to
  `FAILED`. Update example output too.

- [x] **Document the auto-protected paths list** (`docs/verification-gates.md`,
  `dark_factory/verification/runner.py:13-24`). Today the default list includes `:(glob)**/conftest.py`,
  `sitecustomize.py`, `usercustomize.py`, plus `.coveragerc`. Users reading the docs see only the old
  `tests / test.sh / pytest.ini / tox.ini` set.

- [x] **Architecture-layer responsibilities** (`docs/architecture.md:52-78`). The mermaid and the
  prose currently place "Gate Restoration" inside the Sandbox layer's bullet list, but in code that
  responsibility is the `VerificationRunner`'s call into `Sandbox.restore_paths`. Reassign the
  responsibility bullets so the diagram and code match.

- [x] **`doctor` shows the offline path** (`docs/getting-started.md:55-66`). The example output is the
  happy path only; add a second example for "Ollama-only / no Prism" so the documented expectation
  matches what the operator sees when one backend is down.

- [x] **Apple Silicon / Metal compatibility matrix** (`docs/local-inference.md`). `prism` is
  DirectML/CUDA only; there is no `mlx` / Apple Foundation Models fallback. Add a small table clarifying
  which backend supports which GPU family.

- [x] **Drop the unverified "<100ms" worktree claim** (decided 2026-09-30: drop, no benchmark). Files: `README.md:41`,
  `intent.md:38`, `spec.md:144`, `docs/index.md:20,36`, `docs/architecture.md:60`, `docs/getting-started.md:87`,
  `dark_factory/sandbox/worktree.py:20` (docstring), `docs/sdlc/{intent,spec}.md`. **Test:**
  `tests/test_docs_alignment.py::test_no_unverified_performance_claims`.

- [x] **`detect_default_gate_paths()` can't tell a lint/type-check gate's *target* file from a *test/config*
  file** — found in 10.12, **fixed in 10.13** (see below), no longer open.

- [ ] **`LocalCoderHarness._build_context()` auto-detects and inlines *any* file path mentioned in the task
  prompt, in full, with no size cap — including files mentioned only for reference/explanation, not files
  the agent is meant to edit.** Found 2026-09-29 during real dogfooding on this repo itself (not a
  synthetic eval scenario): a task asking to update `docs/cli.md`'s `recover` section, whose prompt also
  named `_reconcile_orphan()` in `dark_factory/orchestrator/engine.py` for context, caused the harness's
  regex path-scanner (`_build_context`, `re.findall(r"[\w/\.-]+\.[a-zA-Z0-9]+", task_prompt)`) to inline the
  **entire 519-line `engine.py`** alongside the 178-line `docs/cli.md`. With both files in context,
  `qwen2.5-coder:14b` abandoned the edit task entirely and produced a prose *explanation* of the
  `DurableEngine` class instead — zero `` ```file: `` blocks, `harness_result.success=False` every one of
  4 attempts (1 initial + 3 healing), `manifest.status=FAILED` with a 0-byte patch and no verification gates
  ever reached (the harness-parse-failure branch never gets to run verification). **Reproduced
  deterministically**: calling `_call_model` directly with just `docs/cli.md` in context succeeded 4/4
  times; adding `engine.py` to context reproduced the exact same derailment on the first try. Real run:
  `run-20260929-200445-95ae65`. **Operator decision (2026-09-29): document only, do not fix in this
  session** — a fix would need to cap/omit large auto-detected reference files (e.g. skip inlining a file
  above some line/byte threshold unless it's also named in `target_files`, or otherwise distinguish
  "files to edit" from "paths mentioned for context") without breaking legitimate small-file context
  auto-detection that the rest of this session's real-model tests already depend on. **Practical workaround
  for operators today**: describe referenced behavior in prose rather than naming the file path, or pass
  `target_files` explicitly instead of relying on prompt-text auto-detection.

---

### 10.8 Pre-Release Blocker — End-to-End Coverage Gaps

**Status: done (2026-09-28).** Source: operator review of `tests/test_e2e.py`. The single existing e2e
test (`test_full_factory_vertical_slice`) only exercised the happy path — `AWAITING_REVIEW` → `APPROVED`
with a deterministic stub harness — so none of the error/lifecycle paths added or touched by Phase 10 had
any full-stack coverage, only unit-level coverage in `test_orchestrator.py`. **Operator decision: this
blocks `0.1.1`**, ranked ahead of 10.7 (doc/ops alignment, non-blocking).

- [x] **e2e coverage for error/lifecycle paths.** `tests/test_e2e.py` now has one full-stack scenario per
  terminal path, each going through the real `DurableEngine.execute_run` (only the harness is a test
  double): `test_e2e_run_deadline_produces_timed_out`, `test_e2e_cancellation_preserves_partial_diff`,
  `test_e2e_empty_patch_ends_failed_not_awaiting_review`, `test_e2e_self_healing_repairs_failing_verification`
  (`healing_attempts == 1`, repaired code lands after approve), and
  `test_e2e_recover_after_crash_completes_full_review_flow` (recover → review → approve → tests green on
  the target repo, not just the DB row).

- [x] **Real local-model e2e call.** `test_e2e_real_local_model_smoke` exercises
  `LocalCoderHarness._call_model` against a real Ollama/Prism instead of a stub harness (closes the gap
  flagged in 10.5's coverage item). Gated behind `LocalCoderHarness.check_health()` (same check
  `dark-factory doctor` performs) — `pytest.skip`s cleanly when neither engine is reachable instead of
  failing CI. Marked `@pytest.mark.local_engine` (registered in `pyproject.toml`); run explicitly with
  `pytest -m local_engine` on a machine with a local model available. Only the wire-level integration and
  terminal-state/telemetry shape are asserted — not the model's output correctness, which is nondeterministic.

- [x] **CLI-level e2e.** `test_e2e_cli_run_and_review_round_trip` drives the real `dark-factory` console
  script as a subprocess (`run` then `review --approve`) against a stub HTTP server standing in for Ollama
  (bound to an ephemeral port passed via the new `--ollama-url`, so it can't collide with a real Ollama on
  the operator's machine) — closing the `cli.py` coverage gap from 10.5. This required adding
  `--storage-dir` (`run`/`list`/`describe`/`review`/`recover`) and `--timeout-minutes`/`--ollama-url`/
  `--prism-url` (`run`) to the CLI, which also closes that part of 10.7's flag-exposure item.

---

### 10.9 Lightweight Performance Tracing

**Status: done (2026-09-28).** Source: operator request ("dodaj tracing żeby policzyć performance"),
scoped via clarification to the lightweight/built-in option: no new dependency and no external tracing
backend (consistent with Zero Cloud Tokens / local-first) — durations are recorded straight onto the
existing `EvidenceManifest` alongside the rest of the evidence, not a separate tracing subsystem.

- [x] **`PhaseTiming` on `EvidenceManifest`** (`domain/types.py`). `PhaseTiming(phase: str,
  duration_sec: float, started_at: str)`; `EvidenceManifest.phase_timings: list[PhaseTiming]`. Populated
  by a module-level `_trace(manifest, phase)` context manager in `orchestrator/engine.py` wrapping:
  `sandbox_create`, `agent_and_verify` (the outer envelope of the harness+healing+verification loop —
  the loop's own internals are already broken down via `model_telemetry.duration_sec` and each
  `StepExecution.duration_sec`), `diff_extract`, and `evidence_preserve` in `execute_run` (including the
  `TIMED_OUT`/`CANCELLED` exit paths), plus `patch_apply` in `review_run`. A `save_run` call is itself the
  thing that would record `evidence_preserve`'s duration, so it can't include its own timing on the first
  write; `execute_run` does one cheap extra `locker.save_run` right after (same patch content, no
  `transcript` arg) so the completed `phase_timings` list actually lands in `manifest.json`. **Tests:**
  `test_execute_run_records_phase_timings`, `test_timed_out_run_records_phase_timings`,
  `test_cancelled_run_records_phase_timings`, `test_review_run_approve_records_patch_apply_phase_timing`.
- [x] **Serialize/deserialize `phase_timings`** in `storage/evidence.py` (`save_run` covers it via
  `asdict`; `load_manifest` reconstructs via `PhaseTiming(**pt)`, same pattern as `StepExecution`).
- [x] **`dark-factory describe` prints a `PHASE TIMINGS` section** (`cli.py`). **Test:**
  `test_cli_describe_prints_phase_timings`.
- [x] Mirrored the `PhaseTiming` addition in `spec.md` §2/§3.4 and `docs/sdlc/spec.md` (byte-identical
  copy, `mkdocs build --strict` green).

---

### 10.10 Correctness-Verified Real-Model E2E

**Status: done (2026-09-28).** Source: operator follow-up on 10.8's `test_e2e_real_local_model_smoke`
("co z kompleksowymi testami" → clarified to: more realistic e2e against the live local Ollama, actually
checking the generated code is correct, not just that the pipeline didn't raise). Both tests are
`@pytest.mark.local_engine` (skip cleanly when no engine is reachable) and confirmed green 4/4 runs against
this operator's real Ollama (`qwen2.5-coder:14b`, `localhost:11434`), ~6-12s total for both.

- [x] **Tightened `test_e2e_real_local_model_smoke`** to require actual success: asserts
  `manifest.status == RunStatus.AWAITING_REVIEW` (previously also accepted `FAILED`), then
  `review_run(approve=True)` and re-runs `pytest` on the target repo to confirm the fix genuinely works.
- [x] **Added a multi-file task e2e** (`test_e2e_real_local_model_multi_file_task`, `calculator_repo`
  fixture): `calculator.py` with `add`/`subtract` implemented and `multiply` missing, `cli.py`'s
  `dispatch()` missing the `"multiply"` branch, task prompt asks for both. Exercises multi-file
  `` ```file: `` block parsing and the self-healing loop against a real model. `max_healing_attempts=5`,
  `timeout_minutes=5` for inference variance headroom; asserts `AWAITING_REVIEW`, approves, confirms both
  files' tests pass on the target repo.

---

### 10.11 Concurrency / Load Tests

**Status: done (2026-09-28).** Source: operator request ("dodaj bardziej rozwiniete testy z loadem").
Scope: exercise `DurableEngine` under concurrent load within one process
(`concurrent.futures.ThreadPoolExecutor`), using fast deterministic harnesses/gates (not the real model —
that's 10.10's job) so the tests run in CI. Confirmed stable across 5 consecutive full-suite runs.

- [x] **Concurrent `execute_run` isolation** (`test_concurrent_execute_run_isolated_sandboxes`): 8 runs
  launched in parallel against one `DurableEngine`/one repo, each its own `run_id` and `GitWorktreeSandbox`.
  Asserts every run reaches `AWAITING_REVIEW` with its own correct, non-cross-contaminated patch and that
  SQLite (WAL mode) ends up with exactly 8 consistent rows.
- [x] **Concurrent `review_run(approve=True)` on the same host repo**
  (`test_concurrent_review_run_serializes_git_mutations`): 8 `AWAITING_REVIEW` runs approved in parallel
  against the *same* `manifest.repo_path` (unlike sandboxes, `activity_apply_patch` mutates the host repo's
  actual working tree directly — `git checkout -b` / `git apply` / `git commit`). **Found a genuine race**:
  with the lock removed, this reliably reproduced `fatal: Unable to create '.git/index.lock': File exists`
  (verified red, then green again after restoring the fix — not just "it passed once"). **Fixed**:
  `DurableEngine` gained a per-instance `threading.Lock()` (`self._review_lock`) serializing just the
  git-mutating section of `review_run`'s approve path. **Known limitation, documented, not fixed here**:
  the lock is per-process — two separate `dark-factory review` CLI invocations (separate OS processes)
  approving concurrently against the same repo are still racy. A cross-process fix (e.g. a flock on
  `.factory/review.lock`) is tracked as backlog, not required for the single-process/embedded-engine usage
  this release targets.

---

### 10.12 More Realistic Real-Model E2E Scenario

**Status: done (2026-09-28).** Source: operator request ("zrob testy bardziej realistyczne"), follow-up on
10.10. 10.10's two real-model tests were "implement this stub" / "add this obviously-missing branch" —
close to a from-scratch toy exercise, not the diagnose-and-fix-without-regressing shape of real usage
described in this project's own `AGENTS.md`/`CLAUDE.md` SDLC (which gates on both `pytest` AND `ruff check`).

- [x] **`test_e2e_real_local_model_realistic_bugfix`** (`textutils_repo` fixture): an existing `slugify()`
  function with a genuine bug (naive `.replace(' ', '-')` doesn't collapse repeated whitespace) — not a
  `TODO` stub. 1 of 3 tests already passes, so a correct fix must not regress it. **Two verification
  gates**, matching real operator usage: `pytest test_text_utils.py` and `python -m ruff check
  text_utils.py` — the fix must also be lint-clean. `@pytest.mark.local_engine`, confirmed 3/3 green
  against the operator's real Ollama (solved first-try, 0 healing attempts, every run).
  - **Found and fixed a real test-design bug in the process**: `VerificationRunner.detect_default_gate_paths()`
    treats every path-looking argv token of every verification step as a protected gate file. A `ruff check
    text_utils.py` gate's own argv names the file the agent is supposed to edit, so the auto-detector would
    protect it and silently revert the model's fix before every verification pass, making the task
    unsolvable. Worked around here with an explicit `protected_paths=["test_text_utils.py"]` on the
    `TaskSpec`. **This heuristic gap in `detect_default_gate_paths()` itself is a real, general limitation**
    (any lint/type-check gate whose argv includes the file being edited hits it) — tracked as a new 10.7
    item, not fixed in `detect_default_gate_paths()` itself here (no argv-position-based fix is obviously
    correct without a protocol change).
  - **Found a genuine model-behavior limitation, not a tool bug, and deliberately scoped around it**: an
    earlier, broader fixture version added an unrelated `truncate()` whose "obviously correct" behavior
    (always append `...`, even past `max_length`) conflicts with the much more common "capped at
    `max_length` including the ellipsis" convention. qwen2.5-coder:14b reliably "fixed" that already-correct
    function anyway across multiple runs — even when the prompt explicitly said not to touch it — evidently
    overriding the instruction with a strong training-data prior, and got stuck reproducing the identical
    (wrong) diff across all 5 healing attempts rather than converging. Real and worth knowing about
    (LLM-generated fixes can silently violate explicit negative constraints when they collide with a common
    convention), but it makes a *correctness* test flaky against a model judgment call, not an objective
    bug — so the fixture was narrowed to one function / one unambiguous root cause instead of "fixed" by
    over-specifying the prompt.

---

### 10.13 Gate-Path Heuristic Fix + Complementary Real-Model Tests

**Source:** operator request ("jedziemy dalej z bardziej kompletnymi/komplementarnymi testami"),
2026-09-29, follow-up on 10.12. Clarified via AskUserQuestion to 3 of 4 proposed items (coverage-% push
declined).

- [x] **Fix `detect_default_gate_paths()`'s lint-target-vs-gate-file heuristic gap** (`verification/runner.py`).
  Added a small denylist of linter/formatter/type-checker tool names
  (`ruff`, `flake8`, `pylint`, `mypy`, `pyright`, `black`, `isort`) in `_LINTER_LIKE_TOOLS`; when a step's
  argv contains one (matched on `Path(arg).stem`, so it catches `ruff`, `python -m ruff`, `/path/to/ruff`
  alike), that step contributes nothing to the auto-detected protected-path set (its target files are what
  the agent must edit, not gate/test files — `_DEFAULT_PROTECTED_PATHS`'s fixed baseline, e.g.
  `tests`/`pyproject.toml`, still applies regardless). Non-lint steps keep prior behavior unchanged.
  **Tests:** `test_default_gate_paths_does_not_protect_lint_target`,
  `test_default_gate_paths_lint_step_alone_still_protects_baseline`; existing
  `test_default_gate_paths_keep_leading_dots`/`test_default_gate_paths_protect_test_runner_config` stay
  green. 10.12's `protected_paths=[...]` workaround is no longer load-bearing but kept as explicit,
  more readable config for that test.

- [x] **Real-Ollama CLI e2e** (`test_e2e_cli_run_and_review_real_ollama`, extends 10.8's
  `test_e2e_cli_run_and_review_round_trip`, which only used a stub HTTP server standing in for Ollama).
  Drives the real `dark-factory` console script (`run` then `review --approve`) as a subprocess against the
  operator's actual Ollama — no stub server, no `--ollama-url` override — proving the CLI entrypoint itself
  (argument parsing, `LocalCoderHarness` wiring, stdout formatting) works with a real model end-to-end, not
  just via the `DurableEngine` library API (10.10/10.12) or a stub HTTP layer (10.8). `@pytest.mark.local_engine`,
  confirmed green.

- [x] **Multi-iteration real self-healing** (`test_e2e_real_local_model_multi_iteration_healing`,
  `csvparse_repo` fixture: quoted-CSV-field parsing, genuinely harder than 10.10/10.12's from-scratch
  tasks, which were all solved first-try). Asserts `manifest.healing_attempts >= 1`, not just
  `== 0`/"eventually AWAITING_REVIEW", so the test actually exercises the repair-prompt feedback loop
  against a real model. **Empirical result across 7 manual runs against qwen2.5-coder:14b: 6/7 converged
  at exactly `healing_attempts == 1`; 1/7 exhausted all 5 attempts and ended `FAILED`.** That ~85%
  convergence rate is genuine model variance on a task that requires real reasoning (a state-machine
  parser), not a test-design bug — verified by inspecting the actual diffs from all 7 runs, which were all
  reasonable attempts at the same correct approach. Documented honestly in the fixture's docstring rather
  than further simplifying the task into something less representative of real self-healing (10.12 already
  showed the failure mode of over-narrowing a task down to "always solved instantly"). This is exactly why
  the test is `@pytest.mark.local_engine` — exploratory/manual, not a CI gate.

---

### 10.14 Self-Healing "Stuck on One Idea" Detection

**Status: done (2026-09-29).** Source: operator follow-up on 10.13's 1/7 real-model healing failure
("popattrz w trace-y" → "w razie czego dodaj"). Forensic analysis of that exact failed run's on-disk
evidence (`manifest.json`, `transcript.log`, `diff.patch`, the SQLite `events` table — still present under
a pytest-retained `tmp_path`) found a precise root cause: the model reproduced the **exact same conceptual
bug on all 6 attempts** (a backward-look escaped-quote check that's dead code because quote characters are
never buffered in the first place), producing byte-identical pytest failures every time — while a
successful run's first retry used a structurally different, correct strategy (forward lookahead)
immediately. Ruled out: not a wire-level/parsing issue (every attempt produced valid file blocks — the
SQLite event sequence shows `SELF_HEALING → VERIFYING` every time) and not a token-budget/truncation issue
(comparable completion-token counts to the successful run). Root cause: `SelfHealingLoop.run_loop` had no
mechanism to detect "the last attempt failed in exactly the same way" and tell the model to abandon its
current approach — it just re-shows the same error, and a model with a subtly wrong mental model can
re-derive a similarly-flawed fix from scratch rather than trying something qualitatively different.

- [x] **Stuck-detection in `SelfHealingLoop.run_loop`** (`verification/healing.py`). Tracks
  `last_failure_signature` (`failed_step.step_id, .exit_code, .stdout, .stderr` — duration/timed_out
  excluded, those vary run to run) and `repeated_failure_streak` across iterations. When a verification
  failure is identical to the immediately preceding one, the next repair prompt gets a new `STUCK NOTICE`
  block (same pattern as the existing tamper `SECURITY NOTICE`): *"Your last fix resulted in the exact same
  test failure as the attempt before it — your current approach is not working. Do not make a small tweak
  to the same logic; use a fundamentally different algorithm or data structure to solve this problem."*
  `run_loop`'s return type grew a 5th field (`repeated_failure_streak: int`, 0 on success), threaded through
  `activity_execute_task_and_verify` (`orchestrator/activities.py`) and `engine.execute_run`.
- [x] **Lightweight evidence note, no new schema** (`engine.py`). A plain exhausted-retries `FAILED` run
  (previously left `operator_notes` unset) now gets: *"...the same failure repeated identically for the
  last N attempts (the model got stuck on one approach...)"* when `repeated_failure_streak >= 1`, or
  *"...each attempt failed differently"* otherwise.
- [x] **Tests**: `test_self_healing_stuck_notice_appears_only_after_a_repeat` and
  `test_self_healing_no_stuck_notice_when_failures_differ` (`tests/test_verification.py`, using
  `FakeSandbox` with prescribed identical/differing `StepExecution` sequences — deterministic, no real
  model needed to verify the mechanism); `test_exhausted_healing_notes_repeated_failure` and
  `test_exhausted_healing_notes_different_failures` (`tests/test_orchestrator.py`, engine-level
  `operator_notes` wiring); updated the 4 pre-existing `SelfHealingLoop.run_loop` call sites in
  `test_verification.py` for the new 5-tuple return (one of them, `test_self_healing_exhausts_budget`,
  already used identical failures both attempts — a perfect pre-existing fit, now also asserts
  `repeated_failure_streak == 1`).
- [x] **Verification**: 94/94 tests green (`ruff check`/`format --check` clean) including a full
  `-m local_engine` run against the real local Ollama. Re-ran the real-model healing test 3 more times
  post-fix: all 3 converged on the first retry (`healing_attempts == 1`), so none exercised the new notice
  — the failure this fix targets is inherently rare (~1/7 previously), so a handful of extra runs isn't
  enough to newly measure its effect either way. No regression; mechanism itself is deterministically
  covered by the `FakeSandbox` unit tests above.
- [x] **Follow-up fix, found while building Phase 12's eval harness (2026-09-29)**: the failure-signature
  comparison used raw `stdout`/`stderr`, but pytest's own summary line ("1 failed in 0.03s") embeds a
  wall-clock duration that differs run to run even when the real outcome is identical — this made
  `test_exhausted_healing_notes_repeated_failure` genuinely flaky (~3/4 failures reproduced locally: same
  code, same test failure, but the streak sometimes failed to increment because the duration substring
  didn't match). Fixed by normalizing `\d+\.\d+s` substrings out of both strings before comparing
  (`_normalize_for_signature` in `healing.py`). **Test**:
  `test_self_healing_treats_differing_only_in_duration_as_the_same_failure`. Re-ran the previously-flaky
  test 5/5 clean after the fix.

---

## Phase 11: Forward-Looking Capabilities (Post-`0.1.x` Decisions)

Items below are unresolved **strategic** decisions surfaced by the adversarial reviews. They are tracked
here so the strategy discussions stay attached to the plan; each item must graduate to a Phase (or be
formally moved to `Non-Goals` in `intent.md`) before work starts.

### 11.A Foundry Local backend
- Investigate the Microsoft Foundry Local / ONNX GenAI surface (`local-coder` skill is referenced from
  `AGENTS.md` but not wired in `LocalCoderHarness`).
- If pursued: implement a third fallback path in `local_coder.py:_call_model` **after** Prism; accept
  `FOUNDRY_URL` env var; add a `--foundry-url` CLI flag in Phase 10.7.
- If not pursued: remove all mentions from `README.md`, `CLAUDE.md`, `AGENTS.md`, `local-inference.md`,
  and `domain/errors.py:25` (Phase 10.7 first step).

### 11.B Optional container isolation (DockerSandbox / rootless)
- Decide between (a) ephemeral Docker container, (b) `bwrap` user-namespace sandbox, (c) keep
  worktree-only and document the limitation. See `Phase 10.5` already-tracked
  *"Stronger isolation for verification steps"*.

### 11.C Temporal worker adapter (Option C realization)
- If pursued: a separate `dark_factory/orchestrator/temporal_adapter.py` module wrapping the existing
  `activity_*` functions with `temporalio.activity.defn` annotations and a workflow class for `execute_run`.
- If not pursued: edit `docs/architecture.md:3` and `activities.py:4` docstring as in Phase 10.7.

### 11.D Custom-harness extension
- Expose a `--harness` flag plus a documented `AgentHarness` protocol so third parties (no new SDK
  import) can plug in their own harness. Required to make `dark-factory run` useful for non-`local-coder`
  workflows.

### 11.E Multi-tenant / shared repo support
- Currently single-tenant / single-workstation (per `intent.md §4 Non-Goals`). Re-evaluate at the
  same time as 11.B/11.C.

### 11.F Hardware coverage matrix
- A single page that tabulates (backend × GPU family × expected model sizes) so an operator can pick a
  configuration without reading three different docs.

> **Operator gate (per `CLAUDE.md`):** Phases 10.6/10.7 ship with the next `0.1.x` release; Phase 11 items
> are *forward-looking* and require explicit approval before any code is written.

---

## Phase 12: Eval Harness & Read-Only Dashboard

**Status: done (2026-09-29).** Source: operator request ("dodajmy jakis frontend do tego, zrtob eval").
Scoped via AskUserQuestion to a **read-only** local dashboard, with eval/benchmark results surfaced
**inside** it (one combined feature). Approved via `/plan` after a Plan-agent design pass over the full
codebase. Follows this repo's own intent → spec → plan → test → code → review SDLC (`AGENTS.md`);
`intent.md` §5 and `spec.md` §3.7/§3.8 updated first.

### 12.1 Companion fix: expose `repeated_failure_streak` on `EvidenceManifest`
- [x] Added `repeated_failure_streak: int = 0` to `EvidenceManifest` (`domain/types.py`).
- [x] `engine.execute_run` assigns it onto `manifest` right after unpacking `activity_execute_task_and_verify`'s
  5-tuple, before any evidence is preserved.
- [x] `storage/evidence.py:load_manifest` deserializes it with `data.get("repeated_failure_streak", 0)` —
  confirmed backward-compatible with a hand-written legacy manifest missing the key entirely.
- [x] `dark-factory describe` prints it when non-zero.
- [x] **Tests:** `test_storage.py::test_evidence_locker_save_and_load` extended +
  `test_load_manifest_defaults_repeated_failure_streak_for_old_manifests`;
  `test_exhausted_healing_notes_repeated_failure` / `_different_failures` (`test_orchestrator.py`) now
  assert `manifest.repeated_failure_streak` directly, not just `operator_notes` text.
- [x] **Found and fixed a real latent flaky-test bug while extending these tests**: the 10.14
  stuck-detector's failure-signature comparison used raw `stdout`/`stderr`, but pytest's own summary line
  ("1 failed in 0.03s") embeds a wall-clock duration that differs run to run even when the real outcome is
  identical — reproduced ~3/4 locally. Fixed in `verification/healing.py` by normalizing `\d+\.\d+s`
  substrings out of both strings before comparing (`_normalize_for_signature`). **Test:**
  `test_self_healing_treats_differing_only_in_duration_as_the_same_failure`. 5/5 clean after the fix.

### 12.2 Eval harness (`dark_factory.eval`)
- [x] New package `dark_factory/eval/__init__.py`.
- [x] `dark_factory/eval/scenarios.py`: extracted `build_primes_repo`, `build_calculator_repo`,
  `build_textutils_repo`, `build_csvparse_repo` out of `tests/test_e2e.py`'s `target_repo`/
  `calculator_repo`/`textutils_repo`/`csvparse_repo` fixtures (mechanical extraction, no behavior change —
  the fixtures are now thin wrappers); `EvalScenario` frozen dataclass; `SCENARIOS` registry populated from
  the same prompts/gates already used by the 4 `@pytest.mark.local_engine` tests.
- [x] `dark_factory/eval/runner.py`: `EvalRunResult`, `EvalReport` (+ `scenario_summary()`), `run_scenario`,
  `run_eval` (drives a **separate** `DurableEngine(storage_dir / "eval-runs")`, never the main journal),
  `save_report`/`load_report`/`list_eval_reports` (JSON under `.factory/evals/<ts>.json`),
  `format_summary()` for CLI output.
- [x] `dark-factory eval` CLI subcommand (`cli.py`): `--scenario` (repeatable), `--repeat`, `--model`,
  `--ollama-url`, `--prism-url`, `--storage-dir`, `--keep-repos`, `--list`; gates on
  `LocalCoderHarness.check_health()`, exits 1 with a clear message if no engine is reachable; exits 1 if any
  scenario converged zero times.
- [x] **Tests (20 new, all green):** `tests/test_eval_scenarios.py` (each builder produces the expected
  repo/bug; registry completeness); `tests/test_eval_runner.py` (deterministic stub harnesses — repeat
  count, convergence/stuck flagging, aggregation math, JSON round-trip, sort order, confirmed eval runs land
  under `eval-runs/` and `.factory/runs/` is never created); `tests/test_cli.py` additions (`--list`,
  unknown-scenario error, health-gate short-circuit); `test_run_eval_real_model_smoke`
  (`@pytest.mark.local_engine`, confirmed green against the real local Ollama) asserting only that a
  well-formed `EvalReport` comes out — never a specific convergence rate (10.12/10.13/10.14 standard).
  Manually verified end-to-end: `dark-factory eval --list` and `--scenario primes --repeat 1` against the
  real engine, inspected the saved JSON report.

### 12.3 Read-only local dashboard (`dark_factory.dashboard`)
- [x] New package `dark_factory/dashboard/__init__.py`.
- [x] `dark_factory/dashboard/server.py`: `DashboardRequestHandler(BaseHTTPRequestHandler)` — `GET`-only
  dispatch (`/`, `/runs/<id>`, `/eval`, `/api/runs`, `/api/eval`); every other verb returns `405`.
  `run_dashboard(storage_dir, port=8420, open_browser=True)` binds `127.0.0.1` only, no host flag.
  **Design correction made during implementation**: reads from a plain `EvidenceLocker` (disk evidence
  only), *not* `DurableEngine`/SQLite — `EvidenceLocker.save_run()` never touches the SQLite journal, so
  seeding evidence directly (the natural way to test/populate a read-only view) left `DurableEngine.list_runs()`
  seeing nothing. Using the disk-based locker throughout is also simpler: no DB connection needed for a
  page that only ever reads (`spec.md` §3.8 updated to match).
- [x] `dark_factory/dashboard/views.py`: pure HTML-building functions — `render_layout`, `render_runs_list`
  (takes `list[EvidenceManifest]`), `render_run_detail` (mirrors `cmd_describe`'s content, including
  `phase_timings` and `repeated_failure_streak`), `render_eval_view` (latest + historical `EvalReport`s,
  plain HTML table). All interpolated values pass through `html.escape()`. `/api/*` endpoints use
  `dataclasses.asdict`.
- [x] **Diff visualization** (operator follow-up, "dodaj jakas vizualizacje diffa", 2026-09-29):
  `render_diff()` renders the unified diff with GitHub-style add/removed line highlighting — no
  syntax-highlighting library, just CSS classes (`diff-add`/`diff-del`/`diff-hunk`/`diff-file`/`diff-meta`/
  `diff-context`) keyed off the standard unified-diff line prefixes, each source line individually escaped.
  Replaces the plain `<pre>{escaped patch}</pre>` in `render_run_detail`. **Tests:**
  `test_render_diff_empty_shows_placeholder`, `test_render_diff_classifies_added_and_removed_lines`,
  `test_render_diff_escapes_line_content`. Manually verified via `curl` against a running dashboard.
- [x] `dark-factory dashboard` CLI subcommand: `--port` (default 8420), `--storage-dir`, `--no-browser`;
  prints the URL, opens a browser tab unless `--no-browser`, serves until `KeyboardInterrupt`.
- [x] Zero new runtime dependency — stdlib only (`http.server`), consistent with `pyproject.toml`'s single
  existing runtime dependency (`requests`) and `intent.md`'s stance against "Heavy, Unwieldy Infrastructure".
- [x] **Tests (21 new, all green):** `tests/test_dashboard_views.py` (render functions against hand-built
  `EvidenceManifest`/`EvalReport` fixtures, incl. HTML-escaping assertions for `<script>`-bearing
  `operator_notes` and diff content); `tests/test_dashboard.py` (a real `ThreadingHTTPServer` instance on an
  ephemeral `127.0.0.1` port, seeded via `EvidenceLocker.save_run(...)` + a saved eval report; real `GET`s
  to every route incl. 404s; one loop asserting `POST`/`PUT`/`DELETE`/`PATCH` all return `405`). No real
  model needed; runs in the default suite. Manually verified end-to-end: started the dashboard, `curl`ed
  every route (200s, one real 404, one real 405) and confirmed rendered HTML in a browser.

### 12.4 Documentation & release hygiene
- [x] `docs/cli.md` gained full `## dark-factory eval` / `## dark-factory dashboard` reference sections +
  summary table rows; `AGENTS.md` diagnostic-commands block gained both; `docs/sdlc/agents.md` mirror
  re-synced byte-identical. `README.md` Quick Start gained both commands. (`CLAUDE.md`'s CLI mentions are
  two illustrative dev-mode examples, not an exhaustive reference — left as-is.)
- [x] `CHANGELOG.md [Unreleased]` entries (Added: eval, dashboard, `repeated_failure_streak`; Fixed: the
  duration-normalization stuck-detector bug from 12.1).
- [x] `mkdocs build --strict` green.

**Verification:** 157 tests total, all green (`ruff check .` / `ruff format --check .` clean;
`pytest tests/ -m "not local_engine" -q` and the full suite including `-m local_engine` against the real
local Ollama both pass); manual checks as noted per-section above.

