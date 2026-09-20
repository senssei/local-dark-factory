# CLI Reference

`local-dark-factory` provides an operator CLI with subcommands for health checks, task submission, audit trail inspection, human review, and crash recovery.

Both `dark-factory` and `local-dark-factory` point to the same binary.

---

## 🛠️ Subcommands Summary

| Command | Purpose |
|---|---|
| [`dark-factory doctor`](#dark-factory-doctor) | Health check for local LLM engines, GPU, and Git. |
| [`dark-factory run`](#dark-factory-run) | Submit an autonomous coding task with real-time transition streaming. |
| [`dark-factory list`](#dark-factory-list) | List all runs recorded in the local SQLite journal. |
| [`dark-factory describe`](#dark-factory-describe) | Inspect full evidence manifest, telemetry, diff, and gate executions. |
| [`dark-factory review`](#dark-factory-review) | Human-in-the-loop review decision (`--approve` or `--reject`). |
| [`dark-factory recover`](#dark-factory-recover) | Clean crashed runs and prune orphaned worktrees. |

---

## `dark-factory doctor`

Validates host environment readiness.

```bash
dark-factory doctor
```

Checks:
- Git binary and version
- NVIDIA GPU name and free VRAM via `nvidia-smi`
- Ollama endpoint connectivity (`http://localhost:11434`) and available models
- Prism CUDA endpoint connectivity (`http://127.0.0.1:5272/v1`)
- Local `.factory/` journal directory path

---

## `dark-factory run`

Executes an autonomous factory run against a repository.

```bash
dark-factory run [OPTIONS] --task "TASK DESCRIPTION"
```

### Options
- `--repo PATH`: Target repository directory (default: `.`).
- `--task TEXT`: Task description and acceptance criteria (**required**).
- `--base-rev REV`: Git commit or branch to branch worktree from (default: `HEAD`).
- `--model NAME`: Local model name (default: `qwen2.5-coder:14b`).
- `--test-cmd CMD`: Command to run for verification. Can be specified multiple times.
- `--retries INT`: Maximum self-healing attempts (default: `3`).
- `--no-verify`: Allow run without verification gates (**DANGEROUS**).
- `--allow-gate-edits`: Allow agent to author or modify test files/gates.

### Example
```bash
dark-factory run \
  --repo /path/to/my-repo \
  --task "Implement exponential backoff retry in client.py" \
  --test-cmd "pytest tests/test_client.py" \
  --retries 3
```

---

## `dark-factory list`

Lists all runs recorded in the SQLite database ordered by creation date descending.

```bash
dark-factory list
```

---

## `dark-factory describe`

Displays the complete audit manifest and unified patch for a given run ID.

```bash
dark-factory describe <RUN_ID>
```

Example:
```bash
dark-factory describe run-20260920-180000-a1b2c3
```

---

## `dark-factory review`

Enforces the Human-in-the-Loop governance gate. Approves or rejects changes created by a run.

```bash
# Approve and commit patch to a new branch
dark-factory review <RUN_ID> --approve --branch feature/retry-logic

# Reject patch with feedback notes
dark-factory review <RUN_ID> --reject --note "Refactor to use asyncio.sleep instead of time.sleep"
```

### Safety Features
- Validates the patch with `git apply --check` before touching the repository.
- Verifies the cryptographic SHA256 digest of the patch matches the manifest recorded during verification.
- Stages only the specific files modified by the patch.

---

## `dark-factory recover`

Recovers runs interrupted by power failures, crashes, or abrupt termination.

```bash
dark-factory recover
```

- Leaves runs awaiting human review (`AWAITING_REVIEW`) intact.
- Marks crashed or orphaned runs as `FAILED`.
- Cleans orphaned sandbox directories and runs `git worktree prune` on affected repositories.
