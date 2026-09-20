# Intent: Sovereign Dark Factory (`06-dark-factory`)

## 1. Problem Statement

Modern software engineering is transitioning from interactive, prompt-by-prompt coding to autonomous, 24/7 background agent factories. Recent prototypes in this space—most notably [Machinist / ESF (`mitkox/esf`)](https://github.com/mitkox/esf)—demonstrate the power of combining durable workflows (Temporal) with isolated microVM execution (CubeSandbox) and deterministic verification.

However, existing implementations suffer from critical systemic flaws that prevent true autonomy and ownership:
1. **Cloud Lock-in & Explosive Token Costs**: Existing agent factories rely on cloud APIs (`anthropic/claude-sonnet-4-5`, DeepSeek cloud). Running autonomous 24/7 loops with multiple test-and-repair iterations racks up unsustainable API bills, exhausts rate limits, and exfiltrates proprietary code and intellectual property to commercial third parties.
2. **Heavy, Unwieldy Infrastructure**: Solutions like Tencent CubeSandbox require specialized microVM daemons and nested virtualization, which are impractical and unstable on standard local developer workstations (WSL2 / Linux).
3. **Operational Drag**: Running a full enterprise Temporal cluster + PostgreSQL container fleet on a local desktop wastes precious CPU and RAM (2–4 GB) that should be allocated to LLM context windows and GPU acceleration.

> **Guiding Principle**: *"Make sure you own your AI. AI in the cloud is not aligned with you; it’s aligned with the company that owns it."*

---

## 2. Proposed Outcome & Vision

We will build **Sovereign Dark Factory** (`dark-factory`): a lightweight, local-first, zero-cloud-token AI Software Factory tailored for developer workstations equipped with NVIDIA RTX GPUs and WSL2/Linux.

The human operator transitions from a "boilerplate typist" to an **AI Factory Manager**. The factory operates autonomously around the clock:
- Tasks are submitted via CLI, scheduled crons, or repository triggers.
- Each task runs in a fast, disposable, isolated sandbox.
- The agent harness executes code modifications using local models powered by our unified router (`05-local-coders`), Ollama (`02-ollama-loadtest`), and Prism CUDA (`03-foundy-local`).
- Deterministic verification gates (`build.sh`, `test.sh`, `pytest`) independently judge success. Failing gates feed error traces back into an AST self-healing loop.
- Verified changes, execution logs, model telemetry, and unified git diffs are preserved in a durable evidence locker.
- The factory manager reviews the verified patch through a Human-in-the-Loop (HITL) gate (`dark-factory review <RUN_ID> --approve / --reject`).

---

## 3. Key Constraints & Local Hardware

1. **Hardware**: NVIDIA GeForce RTX 5070 (12 GB VRAM), 32 GB System RAM, WSL2 on Linux 6.6.
2. **Inference**:
   - Primary reasoning & generation: `qwen2.5-coder:14b` via Ollama (`http://localhost:11434/v1`).
   - Fast triage & refactoring: `qwen2.5-coder:7b` (Ollama) or `phi4-mini` via Prism CUDA (`http://127.0.0.1:5272/v1`).
   - Zero external cloud token usage.
3. **Sandboxing**:
   - Primary: `GitWorktreeSandbox` (sub-100ms startup, zero daemon dependency, isolated working trees).
   - Optional: `DockerSandbox` (ephemeral container when system isolation is requested).
4. **Durable Orchestration**:
   - Zero-dependency embedded SQLite workflow journal (`.factory/factory.db`) for instant state transitions and crash recovery.
   - Optional adapter to Temporal CLI dev server (`temporal server start-dev`).

---

## 4. Non-Goals (Out of Scope)

1. **Cloud Multi-Tenancy**: This is a sovereign, single-tenant, local-first factory for the developer and their infrastructure.
2. **Web SaaS Hosting**: No external public SaaS or user authentication systems. All control is local via CLI and optional localhost dashboard.
3. **Specific Framework Lock-in**: The factory must remain agnostic to project languages (supporting Python, Go, Rust, Node.js, C++, and shell-based repositories).

---

## 5. Success Criteria

- [ ] **Zero Cloud Cost**: Complete end-to-end task run with $0.00 spent on cloud APIs.
- [ ] **Deterministic Gate Enforcement**: Agent declaring "I am done" does not cause a run to pass; only verification scripts exiting 0 pass.
- [ ] **Automatic Self-Healing**: Compiler and test failures are fed back to the local model to iterate on fixes up to `N` retries.
- [ ] **Durable Evidence**: Every run saves `diff.patch`, `manifest.json`, telemetry (tokens/sec, duration from `02-ollama-loadtest`), and full logs.
- [ ] **HITL Review**: Operator can inspect and approve/reject patches with a single command.
