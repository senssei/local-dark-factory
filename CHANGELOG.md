# Changelog

All notable changes to this project are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [SemVer](https://semver.org/).

## [Unreleased]

### Fixed (Phase 14.5 review remediation)
- Adversarial audit: severity allowlisted (dashboard XSS), verdict derived from findings, `CRITICAL` overall badge, LLM text sanitised in CLI output and evidence files, tolerant manifest loading.
- Planner/auditor/mutator: `<think>` blocks and prose around JSON handled, field types validated, prompt fences cannot be closed by diff content, model calls clamped to the run deadline.
- Adversarial mutation: probe cleanup on every exit path, deadline during mutation ends as `TIMED_OUT`, baseline gates re-run after the probe.

### Security
- Python verification runner modules and pytest bootstrap imports are restored before gates, including ignored module/package/bytecode shadows. Explicit protected test paths retain this protection; restoration errors stop gate execution.
- Verification gate protection now also covers test-runner configuration (`pyproject.toml`, `setup.cfg`, `.coveragerc`, and `conftest.py` / `sitecustomize.py` / `usercustomize.py` at any depth). Previously an agent could weaken the gates by editing them.
- `GitWorktreeSandbox.write_file` rejects any path inside `.git` (worktree `gitdir:` pointer hijack).
- `review --approve` refuses to apply a patch onto files with uncommitted changes, so it can no longer commit the operator's work-in-progress.

### Fixed
- `LocalCoderHarness` no longer truncates files that contain their own markdown code fences (e.g. `README.md`); unterminated blocks are discarded instead of written half-complete.
- Gate-path detection used `lstrip("./")`, which mangled `.github/...` into `github/...`.
- `VerificationRunner` now short-circuits the next gate as soon as `task_spec.timeout_minutes` has elapsed, instead of granting a `max(1, int(remaining))` second floor per gate. Honouring spec §202 ("clamps each gate's timeout to the time remaining").
- `get_diff` is independent of user git config (`color.ui`, `diff.noprefix`, `diff.external`, rename detection), is binary-safe, and raises `SandboxError` instead of returning a silent empty patch.
- `parse_patch_files` handles paths with spaces and quoted (non-ASCII) paths; staging uses literal pathspecs.
- `activity_apply_patch` is atomic: a failure after the branch was created restores the original branch, deletes the new one, and reverts touched files.
- A run whose gates pass but whose patch is empty now ends `FAILED` (`empty_patch`) instead of `AWAITING_REVIEW`.

### Added
- `TaskSpec.timeout_minutes` is enforced as a run deadline (`TIMED_OUT`); `RunTimeoutError` carries partial evidence.
- `KeyboardInterrupt` / `SystemExit` end the run `CANCELLED` with evidence saved and the sandbox cleaned up.
- Evidence is persisted before the `AWAITING_REVIEW` transition; `recover()` reconciles a crash in that window from the on-disk manifest.
- `dark-factory run` gained `--timeout-minutes`, `--storage-dir`, `--ollama-url`, and `--prism-url`; `list`/`describe`/`review`/`recover` gained `--storage-dir`, so operators can point the CLI at local engines and a journal location other than the defaults.
- `tests/test_e2e.py` now covers the full vertical slice for every terminal path (`TIMED_OUT`, `CANCELLED`, `empty_patch`/`FAILED`, self-healing, `recover()` after a mid-run crash), a `pytest.mark.local_engine`-gated smoke test against a real Ollama/Prism, and a CLI-level round trip (`dark-factory run` → `review --approve`) driven as a real subprocess.
- Lightweight local performance tracing: `EvidenceManifest.phase_timings` records the wall-clock duration of `sandbox_create`, `agent_and_verify`, `diff_extract`, `evidence_preserve` (every `execute_run` exit path, including `TIMED_OUT`/`CANCELLED`), and `patch_apply` (`review_run`). No external tracing backend — durations are persisted alongside the rest of the evidence and printed by `dark-factory describe`.
- `test_e2e_real_local_model_smoke` (`pytest -m local_engine`) now requires the real model to actually solve the task (`AWAITING_REVIEW` + approved + re-verified), not just reach a clean terminal state; a new `test_e2e_real_local_model_multi_file_task` exercises the same real-model path across two files.
- Concurrency/load tests: `test_concurrent_execute_run_isolated_sandboxes` (8 parallel `execute_run`s, checks per-sandbox isolation and SQLite WAL consistency) and `test_concurrent_review_run_serializes_git_mutations` (8 parallel approvals against the same host repo — see Fixed below).
- `test_e2e_real_local_model_realistic_bugfix` (`pytest -m local_engine`): a diagnose-and-fix-without-regressing scenario against an existing (not stubbed) function, gated on both `pytest` and `ruff check`, matching real operator usage.
- `test_e2e_cli_run_and_review_real_ollama` (`pytest -m local_engine`): drives the real `dark-factory` console script against a real local Ollama (no stub server, no `--ollama-url` override), extending 10.8's stub-backed CLI round trip.
- `test_e2e_real_local_model_multi_iteration_healing` (`pytest -m local_engine`): a quoted-CSV-parsing task that actually exercises the self-healing repair loop against a real model (`healing_attempts >= 1`), rather than tasks solved first-try.
- `test_default_gate_paths_does_not_protect_lint_target` / `test_default_gate_paths_lint_step_alone_still_protects_baseline`: regression coverage for the lint-target gate-protection fix above.
- **`dark-factory eval`**: a repeatable real-model benchmark suite (`primes`, `calculator`, `textutils`, `csvparse` scenarios, extracted from `tests/test_e2e.py`'s real-model fixtures into `dark_factory.eval.scenarios` so both share one implementation). Drives each scenario through a real local model, `--repeat N` times, and reports per-scenario convergence rate, average healing attempts, and whether the stuck-detector fired. Runs land in a separate `.factory/eval-runs/` journal, never the main run history. Reports are saved as JSON under `.factory/evals/<timestamp>.json`.
- **`dark-factory dashboard`**: a local, read-only web dashboard for browsing run history, evidence, and eval reports. Built entirely on the Python standard library (`http.server`) — no new dependency. Binds `127.0.0.1` only (no host flag); every non-`GET` request returns `405`. Run detail pages render the unified diff with GitHub-style add/removed line highlighting (`render_diff`).
- **Adversarial Red-Team Pipeline contracts & storage**: Added `AdversarialFinding` and `AdversarialReport` domain contracts, added `EvidenceManifest.adversarial_report` (backwards-compatible with legacy manifests), and updated `EvidenceLocker.save_run` to persist `adversarial.md` summaries alongside the evidence locker.
- **Local Adversarial Auditor Engine & Orchestrator Integration**: Added `AdversarialAuditor` in `dark_factory.verification.adversarial`, executing structured red-team prompts across 4 dimensions (`anti-cheating`, `boundary`, `security`, `regression`); hooked `activity_adversarial_audit` into `DurableEngine.execute_run` as an audited phase timing (`adversarial_audit`) on green runs, with `--no-adversarial` CLI bypass.
- **Adversarial Red-Team Operator Surfaces**: `dark-factory describe` renders the Red-Team report with severity badges (`CRITICAL`, `WARN`, `PASS`) and category details; `dark-factory review` displays the adversarial audit findings prior to recording review decisions (and supports interactive `[y/N]` prompt in interactive sessions); and the local dashboard (`render_run_detail`) renders the Adversarial Audit card with severity badge styles and XSS-safe escaping.
- **Split-Model Architecture (Planner vs Executor)**: Decoupled high-level reasoning and architectural decomposition from code generation into two sequential phases. Added `LocalPlanner` in `dark_factory.planning`, `ExecutionPlan` domain contract, traced `task_planning` activity in `DurableEngine.execute_run`, `--planner-model` and `--no-plan` CLI options, `plan.md` evidence persistence, and rendering in `dark-factory describe` and the local dashboard.
- **Active Adversarial Test Mutation (Tier 2)**: Added `AdversarialMutator` (`dark_factory.verification.adversarial_mutator`) to synthesize dynamic hostile pytest unit tests (`test_adversarial_probe.py`) probing boundary conditions, edge cases, and anti-cheating violations. Hooked into `DurableEngine.execute_run` under traced phase `adversarial_mutation` when `--mutate-adversarial` / `TaskSpec.mutate_adversarial` is enabled; probe failures feed back into `SelfHealingLoop` to drive code repair. Preserved generated probe code in `EvidenceManifest.adversarial_test_code` and saved as `adversarial_test.py` in the evidence locker, while cleaning up ephemeral probe files from the sandbox worktree to keep the host repository patch clean. Rendered in `dark-factory describe` and the local dashboard.



### Fixed
- `SelfHealingLoop` now detects when a repair attempt fails with the exact same verification outcome as the previous attempt (byte-identical gate/exit code/stdout/stderr, normalized to ignore embedded wall-clock durations like pytest's own "in 0.03s" summary) and adds a `STUCK NOTICE` to the next repair prompt telling the model its current approach isn't working and to try a fundamentally different one — root-caused from a real run where a local model reproduced the same conceptual bug across all 5 healing attempts. A plain exhausted-retries `FAILED` run's `operator_notes` (previously left unset) now says whether it died from a repeated identical failure or from different failures each time, and `EvidenceManifest.repeated_failure_streak` exposes the count directly (`dark-factory describe` prints it).
- `VerificationRunner.detect_default_gate_paths()` no longer protects a lint/type-check gate's own target file. Previously any step whose argv named a linter (`ruff`, `mypy`, ...) had its target file(s) treated as protected gate files and silently reverted to baseline before every verification pass — making it impossible for the agent to actually fix the file a lint gate was checking.
- `review_run`'s approve path is now serialized per `DurableEngine` instance (`threading.Lock`): concurrent approvals against the same host repository used to race on `git checkout -b`/`apply`/`commit` (reproduced as `fatal: Unable to create '.git/index.lock'`) since, unlike sandboxes, patch application mutates the host repo's actual working tree directly.
- `CANCELLED` runs now preserve `diff.patch` via `activity_preserve_evidence` instead of losing whatever the harness had produced before the interrupt.
- `recover()` also flags runs whose DB status already reads `APPROVED`/`REJECTED` but whose on-disk evidence never caught up (crash between the status transition and the final evidence write) as `FAILED`, rather than leaving a silently incomplete `APPROVED` record.
- `recover()`'s orphan-detection status list is now derived from `RunStatus.is_terminal` instead of a hand-maintained SQL string list.
- Git subprocess helpers (`orchestrator/activities.py:_git`, `sandbox/worktree.py`) decode with `errors="replace"`, so a non-ASCII path outside the host locale can no longer surface as an unrelated `UnicodeDecodeError`.
- `Sandbox.restore_paths`'s contract now documents that implementations must honor `:(glob)` pathspec magic, not just literal paths.

### Changed
- Docs and docstrings aligned with the code (plan §10.7): Foundry Local is no longer described as a backend (the harness is Ollama → Prism), `DockerSandbox` moved to Non-Goals in `intent.md`, Temporal Option C is described as a forward-looking seam (no worker registered), the unverified "<100ms" worktree startup claim was dropped, and `recover`, the default protected-paths list, architecture-layer responsibilities, `doctor` with one backend offline, and a GPU compatibility table are documented. `tests/test_docs_alignment.py` guards these decisions and the `docs/sdlc/` mirrors.

## [0.1.0] - 2026-09-20

First public release of **Sovereign Dark Factory** (`local-dark-factory`).

### Added
- **Sandbox Fabric (`dark_factory.sandbox`)**:
  - `GitWorktreeSandbox`: Lightweight, isolated execution environment created via detached git worktrees (`git worktree add --detach`).
  - Path-traversal security guards to prevent modifications outside the worktree.
  - Verification gate restoration mechanism to prevent agents from tampering with test gates.
  - Subprocess execution with strict argv commands, hard timeouts, and idempotent cleanup (`sandbox.destroy()`).
- **Local Inference Harness (`dark_factory.harness`)**:
  - `LocalCoderHarness`: Multi-engine router supporting Ollama (`qwen2.5-coder:14b`), Prism CUDA (`http://127.0.0.1:5272/v1`), and Microsoft Foundry Local.
  - Zero cloud tokens guarantee: strictly local inference with $0.00 cloud API costs.
  - AST-aware patch parsing (`parse_file_blocks`) and generation telemetry collection (tokens, duration, tokens/sec).
- **Deterministic Verification & Self-Healing (`dark_factory.verification`)**:
  - `VerificationRunner`: Authoritative gatekeeper executing deterministic verification scripts (`build.sh`, `test.sh`, `pytest`).
  - Zero-gate safety guard: fails runs where no verification gates are discovered unless explicitly allowed.
  - Self-healing loop: feeds error traces and compiler outputs back into the local model for up to `N` iterative retry attempts.
  - Cumulative telemetry aggregation across multiple retry iterations.
- **Durable Workflow Orchestrator (`dark_factory.orchestrator`)**:
  - `DurableEngine`: SQLite-backed state machine tracking task lifecycle (`PENDING`, `RUNNING`, `VERIFYING`, `HEALING`, `AWAITING_REVIEW`, `APPLIED`, `REJECTED`, `FAILED`).
  - Transactional state transitions and resilient crash recovery (`dark-factory recover`).
  - Human-in-the-Loop review gate with SHA-256 patch verification.
- **Evidence Locker (`dark_factory.storage`)**:
  - `EvidenceLocker`: Structured persistence for unified git diffs (`diff.patch`), run manifests (`manifest.json`), verification logs, and telemetry summaries.
- **CLI & Operator Controls (`dark-factory` / `local-dark-factory`)**:
  - `dark-factory doctor`: Inspects Ollama, Prism, GPU VRAM, git binary, and sandbox fabric.
  - `dark-factory run`: Submits an autonomous coding task with optional timeout and gate overrides.
  - `dark-factory list`: Lists all task runs and their execution states.
  - `dark-factory describe <RUN_ID>`: Prints task manifest, conditions, gate results, and unified diff.
  - `dark-factory review <RUN_ID> --approve [--branch <NAME>]`: Applies verified patch to target branch.
  - `dark-factory review <RUN_ID> --reject [--note <REASON>]`: Rejects and archives run.
  - `dark-factory recover`: Resumes interrupted tasks after system restart.
- **Documentation & CI/CD**:
  - MkDocs Material documentation site with API references, architectural diagrams, and SDLC guides.
  - GitHub Actions CI pipeline testing across Python 3.11 and 3.12 with package wheel smoke-testing.
  - Native GitHub Pages deployment pipeline.
  - OIDC Trusted Publishing workflow for TestPyPI and PyPI.

[Unreleased]: https://github.com/senssei/local-dark-factory/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/senssei/local-dark-factory/releases/tag/v0.1.0

## SDLC unification — 2026-10-02

- Adopt the shared local-sdlc-kit runner and Codex workflow through AGENTS.md and .agents/skills, retaining project-specific checks in sdlc.toml.
- Document independent review, existing operator authorization and truthful reporting of blocked checks.
