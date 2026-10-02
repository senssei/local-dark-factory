# Specification: Sovereign Dark Factory (`local-dark-factory`)

## 1. System Architecture

The Sovereign Dark Factory implements a 6-stage lifecycle for autonomous code modification:

```mermaid
sequenceDiagram
    autonumber
    actor Operator as AI Factory Manager
    participant CLI as dark-factory CLI
    participant Engine as Durable Engine (SQLite)
    participant Sandbox as GitWorktree Sandbox
    participant Harness as LocalCoder Harness
    participant Model as Local LLM (Ollama/Prism)
    participant Gate as Verification Runner
    participant Locker as Evidence Locker

    Operator->>CLI: dark-factory run --repo <path> --task <str> --gates <profile>
    CLI->>Engine: CreateRun(TaskSpec)
    Engine->>Sandbox: Create(base_rev, path)
    Sandbox-->>Engine: Sandbox Ready (isolated worktree)
    
    loop Agent & Self-Healing Loop (max N retries)
        Engine->>Harness: ExecuteTask(task_prompt, context)
        Harness->>Model: Query local LLM (qwen2.5-coder:14b)
        Model-->>Harness: Generated code / patch
        Harness->>Sandbox: Apply modifications
        Engine->>Gate: RunVerification(gates)
        Gate->>Sandbox: Execute(test_argv)
        alt Gate Fails (exit != 0)
            Gate-->>Engine: Verification Failed + Error Trace
            Engine->>Harness: Feed Error Trace for AST Healing
        else Gate Passes (exit == 0)
            Gate-->>Engine: Verification Succeeded
        end
    end

    Engine->>Sandbox: ExtractDiff()
    Sandbox-->>Engine: Unified patch
    Engine->>Locker: SaveManifest(patch, telemetry, logs)
    Engine->>Sandbox: Destroy()
    Engine-->>CLI: Run Awaiting Review (RUN_ID)

    Operator->>CLI: dark-factory review RUN_ID --approve
    CLI->>Engine: ApplyPatchToBranch(RUN_ID)
    CLI-->>Operator: Patch Committed & Merged
```

---

## 2. Core Domain Data Contracts

```python
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime

class RunStatus(str, Enum):
    PENDING = "PENDING"
    CREATING_SANDBOX = "CREATING_SANDBOX"
    AGENT_RUNNING = "AGENT_RUNNING"
    VERIFYING = "VERIFYING"
    SELF_HEALING = "SELF_HEALING"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"

@dataclass
class VerificationStep:
    id: str
    argv: List[str]
    timeout_sec: int = 300
    mandatory: bool = True
    description: str = ""

@dataclass
class TaskSpec:
    repo_path: str
    task_prompt: str
    base_rev: str = "HEAD"
    agent: str = "local-coder"
    model: str = "qwen2.5-coder:14b"
    verification_steps: List[VerificationStep] = field(default_factory=list)
    max_healing_attempts: int = 3
    timeout_minutes: float = 30
    target_files: List[str] = field(default_factory=list)  # files the agent edits; inlined in full as context

@dataclass
class StepExecution:
    step_id: str
    exit_code: int
    stdout: str
    stderr: str
    duration_sec: float
    passed: bool

@dataclass
class PhaseTiming:
    """Wall-clock duration of one named run phase (sandbox_create, agent_and_verify, diff_extract,
    evidence_preserve, patch_apply). Lightweight local performance tracing: no external tracing
    backend, just timings recorded alongside the rest of the evidence."""
    phase: str
    duration_sec: float
    started_at: str

@dataclass
class EvidenceManifest:
    run_id: str
    created_at: str
    completed_at: str
    status: RunStatus
    repo_path: str
    base_rev: str
    resulting_rev: Optional[str]
    patch_path: str
    patch_size_bytes: int
    healing_attempts: int
    verification_results: List[StepExecution]
    model_telemetry: Dict[str, Any]
    phase_timings: List[PhaseTiming] = field(default_factory=list)
    total_cost_usd: float = 0.0
    adversarial_report: Optional[Dict[str, Any]] = None  # findings from the red-team audit gate

@dataclass
class AdversarialFinding:
    severity: str  # "INFO", "WARN", "CRITICAL"
    category: str  # "anti-cheating", "boundary", "security", "regression"
    summary: str
    details: str

@dataclass
class AdversarialReport:
    passed: bool
    summary: str
    findings: List[AdversarialFinding] = field(default_factory=list)

@dataclass
class ExecutionPlan:
    plan_id: str
    summary: str
    invariants: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)
    target_files: List[str] = field(default_factory=list)
    raw_plan: str = ""
```

---

## 3. Component Specifications

### 3.1. Sandbox Layer (`dark_factory.sandbox`)

- **Interface `Sandbox`**:
  - `create(base_rev: str) -> None`: Prepares the sandbox.
  - `execute(argv: List[str], env: Optional[Dict[str, str]] = None, timeout: int = 600) -> StepExecution`: Runs structured argv without shell interpolation risks.
  - `write_file(rel_path: str, content: bytes) -> None`: Writes files into the sandbox.
  - `read_file(rel_path: str) -> bytes`: Reads files out.
  - `get_diff() -> str`: Runs `git diff HEAD` inside the sandbox to generate a clean, deterministic patch.
  - `destroy() -> None`: Cleans up the sandbox idempotently.

- **`GitWorktreeSandbox` (Default)**:
  - Uses `git worktree add --detach <sandbox_path> <base_rev>`.
  - Generates zero container overhead.
  - Sanitizes environment variables to prevent host secret leaks.
  - Deletion via `git worktree remove --force <sandbox_path>`.
  - `write_file` / `read_file` reject path traversal; `write_file` additionally rejects any path that is or lies inside `.git` (the worktree `gitdir:` pointer must never be agent-writable).
  - `get_diff` is independent of user git configuration: it passes `--no-color --no-ext-diff --no-renames --src-prefix=a/ --dst-prefix=b/ --binary` (no rename detection, so every file appears once as `a/X b/X` and deletions are never lost when staging), and a failing `git` command raises `SandboxError` (it never yields a silent empty patch).
  - **Isolation limit (known):** the worktree isolates the *repository*, not the *process*. Verification steps execute on the host with the sanitized environment and network access. Stronger process isolation is tracked in `plan.md` §10.5.

---

### 3.2. Local Agent Harness (`dark_factory.harness`)

- **`LocalCoderHarness`**:
  - Unified local inference harness.
  - Calls local LLM endpoints (Ollama `/api/generate` or Prism `/v1/chat/completions`).
  - Supports automatic engine fallbacks:
    - Primary: Ollama (`qwen2.5-coder:14b`).
    - Secondary: Prism CUDA (`http://127.0.0.1:5272/v1`).
  - Collects token generation counts, elapsed time, and tokens/sec telemetry.
  - **Context window (Ollama):** Ollama silently truncates a prompt that exceeds its context window to about half the window, losing the *start* of the prompt, which is where the `FORMAT RULES` live; the model then answers in prose instead of `file:` blocks. Measured on Ollama 0.34 (plan.md §10.15): the default window is 4096 tokens, and a prompt larger than the window is reported as `prompt_eval_count = num_ctx / 2 + 2` (2050 of 4096, 4098 of 8192). The harness therefore (a) estimates the prompt size (`len(text) / 3` tokens, deliberately pessimistic), (b) sends `options.num_ctx = clamp(estimate + output reserve, 4096, max_num_ctx)`, where the output reserve is at least the size of the inlined files (the model re-emits whole files) and `max_num_ctx` is a constructor argument (default 8192: the largest window that keeps `qwen2.5-coder:14b` entirely in 12 GB of VRAM), (c) fails *before calling the model* with a clear error when the estimate plus reserve exceeds `max_num_ctx`, and (d) when the reply contains no `file:` block and `prompt_eval_count` is within 4 of `num_ctx / 2 + 2` or at least `num_ctx - 16`, adds a probable-truncation explanation naming the window to the failed `HarnessResult` (a heuristic that only explains a failure; a reply with valid file blocks is never discarded because of it). `max_num_ctx` is also the ceiling of the clamp. Model-bound text is bounded so a large input cannot make the pre-flight fail: gate output in a repair prompt is capped at 6000 characters (head plus tail, with a truncation marker), and the diff given to the auditor and to the mutator at 12000 characters (the auditor adds an `INFO` finding when it truncated). The chosen `num_ctx` is recorded in `ModelTelemetry.num_ctx`. Planner, auditor and mutator calls get the same sizing and pre-flight through `_call_model`. Prism's OpenAI-compatible endpoint has no per-request window: only (a) and (c) apply.
  - **Context building (`_build_context`):** if `target_files` is non-empty, exactly those files are inlined in full and prompt-text auto-detection is off. Otherwise (fallback) paths found in the task prompt that exist in the sandbox are auto-detected and inlined in prompt order while their estimated tokens stay within half of `max_num_ctx`; an auto-detected file that would exceed the remaining budget is listed as a one-line stub (`--- File: <path> (<N> lines, not inlined: over the auto-detected context budget; pass --target-file to include it) ---`) and later, smaller files may still fit.
  - **File block protocol:** each file is emitted as `` ```file:<path> `` … `` ``` ``. Parsing is line-based and nesting-aware: a fence with an info string (`` ```python ``) inside a file opens a nested block, a bare fence closes it, and only a bare fence at depth 0 (at least as long as the opening one) terminates the file. File contents may therefore contain balanced markdown code fences (READMEs, docstrings) without being truncated. A block that is never terminated (truncated model output) is discarded, never written half-complete.

- **`OpenCodeHarness`**:
  - Headless driver for local autonomous coding agents.
  - Configures agent runners to use local OpenAI-compatible endpoints.

### 3.2.1. Split-Model Architecture: Planner & Executor (`dark_factory.planning`)

- **Separation of Concerns**:
  - Complex engineering tasks frequently suffer when a single model is forced to perform high-level architectural decomposition and low-level code syntax synthesis simultaneously.
  - The Split-Model Architecture decouples the task lifecycle into two explicit, sequential phases:
    1. **Planning Session (`LocalPlanner`)**: Executes a reasoning model (`planner_model`, e.g. `deepseek-r1:14b` or `qwen2.5-coder:14b`) with a dedicated system prompt. The planner analyzes the repository structure, task prompt, acceptance criteria, and verification gates to produce an `ExecutionPlan` containing architectural invariants, step-by-step implementation strategy, and target files.
    2. **Execution Session (`LocalCoderHarness`)**: Executes a code-specialized model (`model`, e.g. `qwen2.5-coder:14b`). The coder receives the original `TaskSpec` augmented with the structured `ExecutionPlan`, constraining the model to generate targeted, minimal file modifications without architectural drift.
- **Sequential VRAM Execution (12GB Hardware Invariant)**:
  - Planner and Executor run strictly in sequence, never concurrently.
  - Ollama loads and unloads weights sequentially, preventing out-of-memory crashes on single-GPU hardware.
  - When `planner_model == model`, zero model swapping occurs while still benefiting from two-stage chain-of-thought separation.
- **Fail-Safe Planning**:
  - If a reasoning model emits malformed JSON or conversational prose, the planner wraps the raw output into a standard fallback `ExecutionPlan` rather than failing the run.
  - The operator can bypass the planning phase via `--no-plan` (`TaskSpec.skip_plan = True`).
- **Evidence & Operator Surfaces**:
  - The plan is saved as `.factory/runs/<RUN_ID>/plan.md` in the evidence locker.
  - Embedded into `EvidenceManifest.execution_plan`, rendered in `dark-factory describe`, and displayed on the web dashboard.

---

### 3.3. Deterministic Verification & Self-Healing (`dark_factory.verification`)

- **Verification Contract**:
  - Runs each step in `TaskSpec.verification_steps` in strict sequence.
  - Any mandatory step with `exit_code != 0` immediately triggers the healing protocol.
- **Gate Protection**:
  - Before verification, protected paths are restored to `base_rev` (unless `--allow-gate-edits`).
  - Default protected set = every path-like argv token of the configured steps (matched by prefix removal, never character stripping) plus `tests`, `test`, `test.sh`, `pytest.ini`, `tox.ini`, and the test-runner configuration files `pyproject.toml`, `setup.cfg`, `conftest.py` (any depth), `.coveragerc`, `sitecustomize.py`, `usercustomize.py`.
- **No-op is not success**: a run whose gates pass but whose patch is empty ends `FAILED` (`reason: empty_patch`); only a non-empty, verified patch may reach `AWAITING_REVIEW`.
- **P0 runner integrity:** with gate protection enabled, Python `-m` gate modules (including dotted module names) and recognized Python console tools have their root import module/package restored to the trusted baseline before execution. Pytest's `_pytest` and `pluggy` bootstrap imports are protected too. This protection is additive even when explicit `protected_paths` replace test-path defaults. Ignored shadow files, packages and bytecode must be included in restoration; a restoration failure must prevent gate execution. Existing `allow_gate_edits` remains an explicit bypass. Application source remains editable and importable by tests. This is repository tamper protection, not host process isolation or a guarantee for arbitrary dynamic imports or shell-script runners. Normative reference: `docs/verification-gates.md`.
- **Self-Healing Loop**:
  - If a gate fails, the runner packages:
    1. The failing gate command and exit code.
    2. Combined `stderr` and relevant `stdout` output.
    3. The files modified in the current attempt.
  - It creates a repair prompt:
    ```
    Your recent changes failed deterministic verification.
    Gate: {step_id}
    Error Output:
    {error_trace}
    
    Fix the errors so that the verification gate passes cleanly.
    ```
  - Loops up to `max_healing_attempts`. If it fails after all retries, the run status is marked `FAILED` and changes are preserved for operator inspection.

- **Adversarial Red-Team Gate (`dark_factory.verification.adversarial`)**:
  - **Position**: Executes immediately following successful deterministic verification gates, before transitioning to `AWAITING_REVIEW`.
  - **Input**: The unified `diff.patch`, original `TaskSpec`, and gate results.
  - **Execution**: Evaluates the patch using a local critic persona across four dimensions:
    1. *Anti-cheating*: Shortcut implementations, dummy returns, or mocked checks.
    2. *Boundary invariants*: Missing edge-case handlers, zero-length collections, nullability.
    3. *Security*: Traversal attacks, command injection, secret leakage, or unsafe I/O.
    4. *Regression risk*: Architectural drift, broken contracts, or CPU/memory leaks.
  - **Output**: An `AdversarialReport` containing structured findings with severity levels (`INFO`, `WARN`, `CRITICAL`).
  - **Advisory only**: The audit never changes `final_status`; `passed` is derived from the findings (no `WARN`/`CRITICAL`), never taken from model text.
  - **Operator Surface**: Embedded into `EvidenceManifest.adversarial_report`, rendered by `dark-factory describe` and `dark-factory review`, and saved to `.factory/runs/<RUN_ID>/adversarial.md`.
- **Active Adversarial Mutation (`dark_factory.verification.adversarial_mutator`)**:
  - **Position**: When `--mutate-adversarial` is enabled (`TaskSpec.mutate_adversarial = True`), executes after deterministic verification gates pass.
  - **Synthesis**: Queries a local hostile QA model to generate dynamic Python unit test code (`test_adversarial_probe.py`) probing boundary invariants, edge cases, and anti-cheating assertions on the modified functions.
  - **Syntax Safety**: Generated code is parsed with `ast.parse` prior to execution; malformed code is safely rejected without halting the run.
  - **Feedback Loop**: Mutated tests are executed in the sandbox. If an adversarial test fails (`exit_code != 0`), the failure is fed back into `SelfHealingLoop`, forcing the Coder model to iterate until both baseline gates and adversarial tests pass (or healing attempts exhaust).
  - **Integrity**: The probe is LLM-authored code. After it passes (directly or after healing), `test_adversarial_probe.py` is removed and the baseline gates are re-run on the final tree; a failure there fails the run. A deadline hit during mutation yields `TIMED_OUT` with the probe removed and the diff and evidence preserved. Planner, auditor and mutator model calls are clamped to the remaining run deadline.
  - **Evidence**: Mutated test code is captured in `EvidenceManifest.adversarial_test_code` and saved as `adversarial_test.py` in the evidence locker.

- **Performance & Quality Analysis (`dark_factory.analysis`)**:
  - **Position**: After the deterministic gates pass and the patch is non-empty, before `AWAITING_REVIEW` (alongside the adversarial audit; zero model calls). Skipped with `--no-analysis` (`TaskSpec.skip_analysis`).
  - **Resource sampling**: a daemon thread samples, every 2 s while the run is in `agent_and_verify`, GPU VRAM used/total and GPU utilization (one `nvidia-smi` argv call; absent binary or failure means "unavailable", never an error) and host RAM used/total (`/proc/meminfo`; unavailable off Linux). The sampler is stopped and joined on every exit path and must never raise into the run. Result: `ResourceUsage(peak_vram_mb, vram_total_mb, avg_gpu_util_pct, peak_ram_mb, ram_total_mb, samples)`; fields are `None` when unavailable.
  - **Performance analysis** (from evidence already collected): per-phase share of wall time and the dominant phase; model throughput (`tokens_per_sec`) and healing attempts, taken from the run's real telemetry and healing count.
  - **Quality analysis** (stdlib only, on the diff): files/lines added and removed; for added or modified Python functions, `ast`-based cyclomatic complexity and length; whether source files changed without any test file in the patch. Unparseable files, and files over 1 MB, are skipped, never fatal. Diff parsing follows the `@@` hunk line counts, so content lines that look like `---`/`+++` headers are not mistaken for files; deleted and renamed files count as changed.
  - **Hardware fit rules** (thresholds are module constants, defaults for this workstation, RTX 5070 12 GB / 32 GB RAM): peak VRAM > 90 % of total, peak RAM > 85 %, throughput < 10 tok/s, healing attempts >= `max_healing_attempts`, function complexity > 10, function length > 60 lines, source changed without tests. Each yields an `AnalysisFinding(severity, category, summary, details)` with category `performance`, `resources` or `quality` and severity `INFO` or `WARN`.
  - **Advisory only**: never changes `final_status`. Any analysis exception is swallowed into a single `INFO` finding; the run is unaffected.
  - **Evidence**: `EvidenceManifest.analysis_report` (additive, optional), `.factory/runs/<RUN_ID>/analysis.md`; rendered by `describe`, `review` and the dashboard run detail.

---

### 3.4. Durable Workflow Engine (`dark_factory.orchestrator`)

- **Database**: SQLite database stored at `.factory/factory.db`.
- **Durability**:
  - Atomic transaction for every state transition.
  - In-flight runs that crash can be resumed or cleanly rolled back via `dark-factory recover`.
  - Event log table captures all transition events with ISO 8601 timestamps.
- **Lifecycle guarantees**:
  - `TaskSpec.timeout_minutes` is a hard deadline for the whole run (agent + verification); on expiry the run ends `TIMED_OUT`.
  - `KeyboardInterrupt` / `SystemExit` end the run `CANCELLED`; the sandbox is destroyed and evidence saved on every exit path.
  - Evidence (`diff.patch`, `manifest.json`) is persisted **before** the DB transition to `AWAITING_REVIEW`, so a crash can never leave a review-pending run without evidence. `manifest.json` is written last and atomically; `recover()` adopts the outcome of a run whose manifest is readable and whose patch digest matches, and marks every other orphan `FAILED`.
  - The deadline is checked at every phase boundary (before each model call and each verification pass) and clamps each gate's timeout to the time remaining. A single in-flight model call is not interrupted, so a run can overrun by at most one harness call (`LocalCoderHarness.timeout`).
  - `review --approve` is atomic with respect to the host repository: if applying fails after a branch was created, the original branch is restored and the new branch deleted.
- **Performance tracing**: `EvidenceManifest.phase_timings` records the wall-clock duration of `sandbox_create`, `agent_and_verify`, `diff_extract`, and `evidence_preserve` (`execute_run`), and `patch_apply` (`review_run`) — recorded on every exit path, including `TIMED_OUT` and `CANCELLED`. This is the entire tracing mechanism: no external backend, just timings alongside the rest of the evidence (Zero Cloud Tokens / local-first). `dark-factory describe` prints them.

---

### 3.5. Evidence Locker (`dark_factory.storage`)

Stored at `.factory/runs/<RUN_ID>/`:
- `diff.patch`: Unified diff of all modifications.
- `manifest.json`: Full `EvidenceManifest` data contract.
- `transcript.log`: Complete stdout/stderr trace of agent and verification runs.
- `telemetry.json`: GPU and model performance stats.

---

### 3.6. CLI & Operator Controls (`dark_factory.cli`)

- `dark-factory doctor`: Verifies Ollama, Prism, GPU VRAM, git binary.
- `dark-factory run`: Submits a task. `--target-file PATH` (repeatable) names the files the agent is to edit; they become `TaskSpec.target_files` and are the harness's only inlined context (see §3.2).
- `dark-factory status [RUN_ID] [--watch]`: Streams execution status.
- `dark-factory describe RUN_ID`: Prints manifest, conditions, and diff.
- `dark-factory review RUN_ID --approve [--branch <name>]`: Applies the patch to the target branch.
- `dark-factory review RUN_ID --reject [--note <reason>]`: Rejects and archives the run.

---

### 3.7. Eval Harness (`dark_factory.eval`)

- **Purpose**: a repeatable, scriptable benchmark for measuring self-healing convergence against a real
  local model, replacing ad-hoc one-off scripts.
- **`EvalScenario`** (`dark_factory.eval.scenarios`): a frozen dataclass — `name: str`, `description: str`,
  `build_repo: Callable[[Path], None]` (scaffolds a throwaway git repo with a specific, known bug at the
  given path), `task_prompt: str`, `verification_steps: Callable[[], list[VerificationStep]]` (a factory,
  since argv embeds `sys.executable`), `protected_paths: list[str]`, `max_healing_attempts: int`,
  `timeout_minutes: float`. `SCENARIOS: dict[str, EvalScenario]` is the fixed registry (`primes`,
  `calculator`, `textutils`, `csvparse` at introduction). The same `build_*_repo` functions back both this
  registry and the `pytest` fixtures in `tests/test_e2e.py` — one scaffolding implementation, not two.
- **`EvalRunResult`** (`dark_factory.eval.runner`): one real `execute_run` attempt — `scenario`, `run_id`,
  `converged: bool` (`status == AWAITING_REVIEW`), `status`, `healing_attempts`,
  `repeated_failure_streak_fired: bool`, `duration_sec`, `prompt_tokens`, `completion_tokens`,
  `tokens_per_sec`, `operator_notes`.
- **`EvalReport`**: `started_at`, `finished_at`, `model`, `ollama_url`, `prism_url`,
  `results: list[EvalRunResult]`, `scenario_summary()` (per-scenario convergence rate and average healing
  attempts). Persisted as JSON at `.factory/evals/<ISO-timestamp>.json`.
- **Isolation invariant**: `run_eval(...)` drives scenarios through a **separate**
  `DurableEngine(storage_dir / "eval-runs")`, never the operator's main `.factory` run journal — throwaway
  scaffold-repo runs must never appear in `dark-factory list`/`review` or the dashboard's Runs view.
- **CLI**: `dark-factory eval [--scenario NAME ...] [--repeat N] [--model M] [--ollama-url U] [--prism-url U]
  [--storage-dir D] [--keep-repos] [--list]`. Gates on `LocalCoderHarness.check_health()`; exits `1` with a
  clear message (no silent degradation) when neither Ollama nor Prism is reachable. Never invoked by the
  default `pytest` suite (real-model, non-deterministic by nature — only `-m local_engine`, run by hand).

---

### 3.8. Local Dashboard (`dark_factory.dashboard`)

- **Purpose**: local, browser-based visibility into run history, evidence, and eval reports.
- **Read-only invariant**: the dashboard never mutates state. `DashboardRequestHandler` implements only
  `GET` routes (`/`, `/runs/<id>`, `/eval`, `/api/runs`, `/api/eval`); every other HTTP method returns
  `405 Method Not Allowed`. There is no approve/reject/submit action anywhere in the UI or API.
- **Network invariant**: `run_dashboard(storage_dir, port=8420, open_browser=True)` binds to `127.0.0.1`
  only — there is no `--host`/bind-address flag. The dashboard is never reachable from another machine.
- **No new dependency**: implemented entirely on the Python standard library (`http.server`). No web
  framework, no template engine — HTML is built by plain functions in `dark_factory.dashboard.views` with
  every interpolated value passed through `html.escape()`.
- **Data sources**: `EvidenceLocker.list_runs()`/`load_manifest()`/`load_patch()` for the Runs view — disk
  evidence only, deliberately not `DurableEngine`/SQLite, so the dashboard never opens a database connection
  for what is a purely read-only view (same underlying evidence `dark-factory list`/`describe` expose, just
  not routed through the SQLite journal); `dark_factory.eval.runner.list_eval_reports()`/`load_report()` for
  the Eval view. The dashboard reads `.factory/` state; it never triggers `execute_run`/`review_run` itself.
- **CLI**: `dark-factory dashboard [--port 8420] [--storage-dir D] [--no-browser]`.


## Workspace SDLC unification — 2026-10-02

Scope authorized by the operator's request to unify SDLC across projects 01–08. The workflow is intent → spec → plan → test (red) → code → independent review. Existing domain invariants and adversarial findings remain in force.

- Kit-owned runner, five skills, pre-commit hook and Cursor rule come from the sibling `local-sdlc-kit`; install/update with its installer, never maintain project forks of those files.
- `AGENTS.md` carries the same kit process section in every project; project-specific language, hardware, privacy and execution rules stay outside that section. Harness adapters point to `AGENTS.md`.
- `sdlc.toml` declares the actual checks, red command, timeout and changelog paths. The public gate command is `python3 scripts/sdlc_check.py`; selection uses `--only NAME`, red uses `--red ID`. Gate tooling requires Python 3.11+ independently of product runtime support.
- Migration preserves existing verification controls. Project-specific changed-line lint in Prism remains a separate helper; common runner logic must not absorb language-specific behavior. Pytest collection errors and missing unittest ids must be NOT RED.
- Missing/invalid gate configuration or unknown checks fail explicitly. Missing optional documentation tooling may only skip where the prior gate allowed it. A skipped or unavailable check is reported, not presented as verified.
- 01 gains static Python compilation and JSON/configuration checks; live Windows probes remain manual. 04 gains its existing Astro build as the gate; neither project claims a behavioral test suite that does not exist. Their red interfaces are configured for future unittest/Node test ids and reject missing tests.
- Workspace consistency checks compare installed kit-owned files and process sections with the kit source. Project check sets stay distinct; no common lowest-denominator test suite is imposed.
- Implementation status is recorded separately from verification. Plan boxes remain open until the complete project gate passes; unrelated pre-existing failures are preserved and reported. No commits, pushes, real engine calls or automatic hook activation are part of this change.

### Codex execution contract

Codex reads project AGENTS.md and routes through `.agents/skills/sdlc`. A natural-language request is sufficient; `$sdlc` is an explicit entry. Gate checks receive the selected comparison base through `SDLC_BASE`. Full `scripts/sdlc_check.py` is also configured in `.github/workflows/sdlc.yml`; existing CI jobs remain. A sandbox-blocked check remains unverified. Operator authorization persists within the requested scope.
