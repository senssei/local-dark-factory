# Getting Started

This guide explains how to install `local-dark-factory`, verify your local hardware and inference engines, and run your first autonomous software factory task.

---

## 💻 Prerequisites

- **OS**: Linux / WSL2 (Ubuntu 22.04+ or Debian 12+)
- **Python**: 3.11 or 3.12
- **Git**: 2.30+ installed and on `$PATH`
- **Inference Hardware**:
  - NVIDIA RTX GPU (e.g. RTX 5070 12GB) with CUDA drivers, **OR**
  - Apple Silicon Mac (M-series with Metal)
- **Local Inference Engine**:
  - [Ollama](https://ollama.com) running locally on port `11434` with a code model (e.g. `qwen2.5-coder:14b`), **AND/OR**
  - [Prism](https://github.com/senssei/03-foundy-local) CUDA accelerator running on port `5272`.

---

## 📦 Installation

### From PyPI
```bash
pip install local-dark-factory
```

### From Source (Development)
```bash
git clone https://github.com/senssei/local-dark-factory.git
cd local-dark-factory
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,docs]"
```

Verify the installation:
```bash
dark-factory --help
# or
local-dark-factory --help
```

---

## 🩺 System Health Check (`doctor`)

Run `doctor` to verify your GPU drivers, git installation, and local LLM connectivity:

```bash
dark-factory doctor
```

Example output:
```text
⚡ Sovereign Dark Factory System Diagnostics
==================================================
✅ Git:                   INSTALLED (git version 2.43.0)
✅ NVIDIA GPU:            NVIDIA GeForce RTX 5070 (12282 MiB, 11500 MiB free)
✅ Ollama:                ONLINE (http://localhost:11434)
   Available models (3): qwen2.5-coder:14b, llama3.1:8b, mistral:7b
✅ Prism CUDA:            ONLINE (http://127.0.0.1:5272/v1)
📁 Factory Journal:       /home/senssei/workspace/.factory
==================================================
All tasks execute 100% locally with zero cloud token cost.
```

---

## 🚀 Running Your First Task

Navigate to any git repository that has a test suite:

```bash
cd /path/to/my-project
```

Submit a coding task to the dark factory:

```bash
dark-factory run \
  --task "Fix division by zero exception in calculate_ratio() and add test" \
  --test-cmd "pytest tests/test_calc.py"
```

The factory will:
1. Create a detached git worktree sandbox in `<100ms`.
2. Inspect prompt and repository context.
3. Call your local LLM to generate the implementation.
4. Apply the modifications inside the isolated sandbox.
5. Restore any protected test files from the base commit to prevent cheating.
6. Execute the deterministic verification gates (`pytest tests/test_calc.py`).
7. If tests fail, feed compiler / test errors back into the self-healing loop.
8. When all gates pass, preserve the unified diff, telemetry, and execution transcript in the evidence locker.
9. Pause and await human review.

---

## 🧐 Reviewing and Approving Changes

Inspect the run:
```bash
dark-factory describe run-20260920-180000-a1b2c3
```

Approve and apply the patch to a new git branch:
```bash
dark-factory review run-20260920-180000-a1b2c3 --approve --branch feature/fixed-ratio
```

Or reject the patch:
```bash
dark-factory review run-20260920-180000-a1b2c3 --reject --note "Needs type annotations on helper functions"
```
