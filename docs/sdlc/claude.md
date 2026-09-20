# CLAUDE.md — Operating Manual for Sovereign Dark Factory (`local-dark-factory`)

This repository is **Sovereign Dark Factory**: a local-first, zero-cloud-token autonomous AI Software Factory orchestrator running on Linux/WSL2 with NVIDIA RTX 5070 GPU hardware.

---

## 🚀 Commands & Development Workflow

### Python Environment & Dependencies
```bash
# Set up virtualenv
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,docs]"

# Run tests
pytest tests/ -v

# Run linting & formatting
ruff check .
ruff format --check .

# Run dark-factory CLI in dev mode
dark-factory doctor
dark-factory run --help
```

---

## 🏛 Architecture & Component Layout

```text
dark_factory/
├── domain/         # Pure data contracts (TaskSpec, RunStatus, EvidenceManifest)
├── sandbox/        # Isolated execution fabrics (GitWorktreeSandbox)
├── harness/        # Agent runners (LocalCoderHarness)
├── verification/   # Deterministic test runners and AST self-healing loop
├── orchestrator/   # SQLite-backed durable workflow state machine
├── storage/        # Evidence locker (.factory/runs/<RUN_ID>/...)
└── cli.py          # Operator CLI entrypoint (doctor, run, list, describe, review, recover)
```

---

## ⚖️ Non-Negotiable Core Rules

1. **Zero Cloud Tokens**:
   - Never introduce dependencies on Anthropic, OpenAI, or other paid cloud APIs.
   - All model calls must go through the local stack (Ollama `http://localhost:11434`, or Prism `http://127.0.0.1:5272/v1`).
2. **Deterministic Verification is Authoritative**:
   - The LLM *never* decides if it succeeded. Only verification exit codes decide.
   - An exit code of `0` on all mandatory verification gates is required for a run to be marked `AWAITING_REVIEW`.
3. **Sandbox Isolation**:
   - Agents must never modify the host repository directly during a run.
   - All work happens inside isolated worktrees (`GitWorktreeSandbox`).
   - Sandboxes must be completely and idempotently cleaned up on every exit path (success, failure, cancellation, timeout).
4. **Structured Argv Only**:
   - Never execute arbitrary shell strings without quoting. Verification and sandbox commands must accept `list[str]` (argv) to prevent shell injection.
5. **Durable Evidence**:
   - Every run must preserve its `diff.patch`, `manifest.json`, stdout/stderr transcripts, and local model telemetry.

---

## 🧠 Local AI Skills Integration

When writing or refactoring code in this repository, leverage our local skills and engines:
- **`local-coder`**: Unified multi-engine router across Ollama, Prism CUDA, and Foundry Local.
- **`ollama-coder`**: Direct Ollama CLI (`qwen2.5-coder:14b`, `llama3.1:8b`).
- **`foundry-coder`**: Direct Prism / Foundry Local connector.
- Status check: `dark-factory doctor`
