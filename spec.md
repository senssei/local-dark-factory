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
    timeout_minutes: int = 30

@dataclass
class StepExecution:
    step_id: str
    exit_code: int
    stdout: str
    stderr: str
    duration_sec: float
    passed: bool

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
    total_cost_usd: float = 0.0
```

---

## 3. Component Specifications

### 3.1. Sandbox Layer (`dark_factory.sandbox`)

- **Interface `Sandbox`**:
  - `create(base_rev: str) -> None`: Prepares the sandbox.
  - `execute(argv: List[str], env: Optional[Dict[str, str]] = None, timeout: int = 600) -> StepExecution`: Runs structured argv without shell interpolation risks.
  - `write_file(rel_path: str, content: bytes) -> None`: Writes files into the sandbox.
  - `read_file(rel_path: str) -> bytes`: Reads files out.
  - `get_diff() -> str`: Runs `git diff HEAD` inside the sandbox to generate a clean patch.
  - `destroy() -> None`: Cleans up the sandbox idempotently.

- **`GitWorktreeSandbox` (Default)**:
  - Uses `git worktree add --detach <sandbox_path> <base_rev>`.
  - Generates zero container overhead (<100ms startup).
  - Sanitizes environment variables to prevent host secret leaks.
  - Deletion via `git worktree remove --force <sandbox_path>`.

- **`DockerSandbox` (Optional)**:
  - Ephemeral container with restricted volume mounts and memory limits.

---

### 3.2. Local Agent Harness (`dark_factory.harness`)

- **`LocalCoderHarness`**:
  - Unified local inference harness.
  - Calls local LLM endpoints (Ollama `/api/generate` or Prism `/v1/chat/completions`).
  - Supports automatic engine fallbacks:
    - Primary: Ollama (`qwen2.5-coder:14b`).
    - Secondary: Prism CUDA (`http://127.0.0.1:5272/v1`).
    - Tertiary: Microsoft Foundry Local.
  - Collects token generation counts, elapsed time, and tokens/sec telemetry.

- **`OpenCodeHarness`**:
  - Headless driver for local autonomous coding agents.
  - Configures agent runners to use local OpenAI-compatible endpoints.

---

### 3.3. Deterministic Verification & Self-Healing (`dark_factory.verification`)

- **Verification Contract**:
  - Runs each step in `TaskSpec.verification_steps` in strict sequence.
  - Any mandatory step with `exit_code != 0` immediately triggers the healing protocol.
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

---

### 3.4. Durable Workflow Engine (`dark_factory.orchestrator`)

- **Database**: SQLite database stored at `.factory/factory.db`.
- **Durability**:
  - Atomic transaction for every state transition.
  - In-flight runs that crash can be resumed or cleanly rolled back via `dark-factory recover`.
  - Event log table captures all transition events with ISO 8601 timestamps.

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
- `dark-factory run`: Submits a task.
- `dark-factory status [RUN_ID] [--watch]`: Streams execution status.
- `dark-factory describe RUN_ID`: Prints manifest, conditions, and diff.
- `dark-factory review RUN_ID --approve [--branch <name>]`: Applies the patch to the target branch.
- `dark-factory review RUN_ID --reject [--note <reason>]`: Rejects and archives the run.
