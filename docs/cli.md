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
| [`dark-factory eval`](#dark-factory-eval) | Run the repeatable real-model benchmark suite. |
| [`dark-factory dashboard`](#dark-factory-dashboard) | Launch the local, read-only web dashboard. |

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
- `--target-file PATH`: File the agent is to edit (repeatable). Exactly these files are inlined in full as the model's context and prompt-text auto-detection is switched off. Without it, files named in the task are auto-detected and inlined only while they fit a token budget; larger ones are listed as stubs. A path that does not exist yet is a file to create.
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

Example output:
```text
Recovered 2 run(s) and pruned orphaned sandboxes.
 - run-20260929-200445-95ae65
 - run-20260929-201112-3fc2a0
```

- Leaves runs awaiting human review (`AWAITING_REVIEW`) intact.
- Settles each crashed or orphaned run from its evidence. The recorded outcome is adopted only when the manifest proves it: `AWAITING_REVIEW` when the patch digest still matches `manifest.json`, and `FAILED`, `TIMED_OUT` or `CANCELLED` as recorded. Every other case is marked `FAILED`: no readable manifest, a missing or mismatching patch digest, or a manifest in any other status.
- Flags runs the database shows as `APPROVED` or `REJECTED` but whose evidence never caught up (a crash during review) as `FAILED`: an `APPROVED` run needs a manifest with `APPROVED` status and a resulting revision, a `REJECTED` run needs one with `REJECTED` status and a completion time. Check the repository by hand after such a run.
- Cleans orphaned sandbox directories and runs `git worktree prune` on affected repositories.

---

## `dark-factory eval`

Runs a standardized suite of real-model tasks and reports self-healing convergence — a repeatable
replacement for one-off manual test scripts. Requires a real local engine (Ollama or Prism); this is an
operator-triggered tool, never run by the default `pytest` suite.

```bash
# List available scenarios
dark-factory eval --list

# Run every scenario once
dark-factory eval

# Run a specific scenario 3 times
dark-factory eval --scenario csvparse --repeat 3
```

### Options
- `--scenario NAME`: Scenario to run (repeatable; default: all registered scenarios).
- `--repeat INT`: Number of attempts per scenario (default: `1`).
- `--model NAME`: Local model name (default: `qwen2.5-coder:14b`).
- `--ollama-url URL` / `--prism-url URL`: Local engine endpoints.
- `--storage-dir PATH`: Journal directory (default: `.factory`).
- `--keep-repos`: Keep scaffolded scenario repos on disk for inspection instead of deleting them.
- `--list`: Print available scenarios and exit.

Scenario runs are driven through a **separate** journal (`.factory/eval-runs/`), never the main run
history, so they never appear in `dark-factory list`/`review`. Reports are saved as JSON under
`.factory/evals/<timestamp>.json` and are viewable in the [dashboard](#dark-factory-dashboard)'s Eval view.

---

## `dark-factory dashboard`

Launches a local, **read-only** web dashboard for browsing run history, evidence, and eval reports.

```bash
dark-factory dashboard
```

- Binds to `127.0.0.1` only — there is no host/bind-address flag; the dashboard is never reachable from
  another machine.
- No write actions anywhere: every non-`GET` request returns `405 Method Not Allowed`. Approve/reject a run
  via `dark-factory review`, not the dashboard.
- Built entirely on the Python standard library (`http.server`) — no new dependency.
- Run detail pages render the unified diff with GitHub-style add/removed line highlighting.

### Options
- `--port INT`: Port to listen on (default: `8420`).
- `--storage-dir PATH`: Journal directory (default: `.factory`).
- `--no-browser`: Do not auto-open a browser tab.
