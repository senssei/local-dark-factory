# Review Policy & Governance (`REVIEW.md`)

This document outlines the **Human-in-the-Loop (HITL)** governance and review policy for the **Sovereign Dark Factory**.

---

## 1. The Factory Manager's Mandate

In the AI-Native SDLC, the human engineer is no longer responsible for boilerplate typing; they are the **AI Factory Manager**. The factory runs autonomously 24/7, but it **never decides what ships to production**. 

A run that finishes all verification gates enters the `AWAITING_REVIEW` state and pauses. The factory manager reviews the evidence before any code touches the main branch.

```text
Task Completed → Verification Passed → AWAITING_REVIEW (Paused) → Manager Decision → Applied/Merged
```

---

## 2. Review Checklist

Before approving any run (`dark-factory review <RUN_ID> --approve`), the operator should review:

### A. Verification Evidence
- [ ] Did all mandatory verification gates pass with exit code `0`?
- [ ] Were any tests skipped or bypassed?
- [ ] How many self-healing attempts were required? (A high number of attempts may indicate fragile code).

### B. Patch Integrity (`diff.patch`)
- [ ] Does the diff touch only files within the task scope?
- [ ] Are there unintended file deletions or formatting thrashing?
- [ ] Does the patch introduce any new, untyped dependencies?

### C. Security & Cleanliness
- [ ] Are there any hardcoded secrets, tokens, or environment dumps?
- [ ] Does the code adhere to project conventions defined in `CLAUDE.md` / `AGENTS.md`?

### D. Telemetry & Performance
- [ ] Confirm $0.00 cloud spend.
- [ ] Inspect tokens/second and total duration from `telemetry.json`.

---

## 3. Operator Review Commands

```bash
# 1. Describe the run and inspect its manifest and patch:
dark-factory describe <RUN_ID>

# 2. Approve the change (creates a git commit on the designated branch):
dark-factory review <RUN_ID> --approve --branch feature/automated-update

# 3. Reject the change with an explanatory note:
dark-factory review <RUN_ID> --reject --note "Refactor uses recursion; prefer iterative approach"

# 4. Trigger rework with operator notes:
dark-factory run --rework-from <RUN_ID> --task "Use iterative approach instead of recursion"
```

## Shared SDLC review — Codex

Read `AGENTS.md`, `intent.md`, `spec.md` and the current phase in `plan.md`. Review the actual working diff, including untracked files, with independent context. Findings must name severity, file/line and a reproducible scenario. Record the exact gate command, exit status and any sandbox limitations; a blocked check is not a pass. Existing operator authorization covers the requested implementation; commits, pushes and releases need their own authorization.

Project checks: Verify baseline tests, worktree boundaries and auditor failure handling; local-engine tests require separate explicit evidence.

Migration verification, 2026-10-02: `python3 scripts/sdlc_check.py` exited 0 with authorized local socket access (219 tests passed, 6 local-engine tests deselected; lint, format, docs, changelog PASS). `python3 ../.sdlc/test_unification.py` exited 0 (2 passed). Prior independent migration review and re-review are recorded in `plan.md`; this follow-up changed verification records only. No real-engine checks or shipping actions were performed.

## P0 runner integrity — 2026-10-02

Scope: runner/import-path tamper protection in `verification/runner.py`, `sandbox/base.py`, `sandbox/worktree.py`, with `tests/test_runner_integrity.py`. Reviewed against the P0 spec and plan only; earlier uncommitted product work was excluded.

Independent reviewer: fresh stateless local Ollama `llama3.1:8b` session, supplied the P0 spec, scoped source diff and complete regression file without author conversation. Report: “NO FINDINGS.” It checked ignored module/package/bytecode shadows, custom protection, restoration failure, unrelated environment preservation and application imports. This is review evidence, not operator shipping approval.

Prior fresh local `qwen2.5-coder:7b` review repeated vague high-severity restoration claims until the output limit; no reproducible scenario was supplied. It was treated as inconclusive, not accepted as a clean review. The ignored-shadow cases and explicit-protection cases pass on real worktrees; restoration commands check their exit codes and residual files. No actionable finding remained after the separate Llama review.

Verification: `python3 scripts/sdlc_check.py` exited 0 with authorized local socket access: 236 passed, 6 local-engine tests deselected; lint, format, strict docs and changelog PASS. Red-first evidence covers the original bypass, all twelve shadow variants, restoration failure and application imports. The seventeen P0 regressions pass. Scope limits: arbitrary transitive imports, shell-script runners and OS process isolation remain outside this fix. No commits, pushes or releases.

## Phase 15 performance & quality analysis — 2026-10-02

Independent reviewer: fresh general-purpose Claude subagent given the spec, plan and diff only. Seven findings (1 HIGH, 3 MEDIUM, 3 LOW); five fixed test-first, one spec correction, one not a defect (sampling scope matches spec). Fixes were verified by tests, not re-reviewed independently. Gate: `python3 scripts/sdlc_check.py` exited 0.

## Phase 10.15 context window — 2026-10-02

Independent reviewer: fresh general-purpose Claude subagent given the spec, plan and diff. Six findings (1 HIGH, 2 MEDIUM, 3 LOW): five fixed test-first, one left as is (a rejected `--target-file` path renders as an unreadable stub). Real-model confirmation ran through the CLI against the local Ollama (scratch clone, `qwen2.5-coder:14b`); the window measurement table is in `plan.md` §10.15. Fixes were verified by tests, not re-reviewed independently. Gate: `python3 scripts/sdlc_check.py` exited 0.

## DF-LIVE-04 healing attempt counting — 2026-10-04

Independent reviewer: fresh stateless research subagent given the spec, plan and diff. Report: “NO FINDINGS.” Checked `healing_attempts` initialization, budget checks on harness and verification failure, bounds checking (`healing_attempts <= max_retries`), prompt formatting, and regression tests. Gate: `python3 scripts/sdlc_check.py` exited 0 (341 passed, 7 deselected).

## DF-LIVE-05 eval campaign resilience and backend error handling — 2026-10-04

Independent reviewer: fresh stateless research subagent given the spec, plan and diff. Four findings:
1. [HIGH] `run_scenario` discarded completed attempts on `KeyboardInterrupt`/`SystemExit`, preventing `run_eval` from persisting partial reports: Fixed test-first (`test_df_live_05_run_eval_keyboard_interrupt_saves_partial_report`) by passing an accumulator `results` list into `run_scenario` and recording each attempt in-place before re-raising.
2. [MEDIUM] `consecutive_backend_errors` reset per scenario rather than halting the campaign across scenarios: Fixed test-first (`test_df_live_05_consecutive_backend_errors_across_scenarios_halts_campaign`) by propagating consecutive errors into `run_scenario` and halting subsequent scenarios once 3 consecutive errors occur.
3. [MEDIUM] Missing test coverage for `run_eval` partial report saving on `KeyboardInterrupt` and `cmd_eval` exit code 130: Fixed by adding explicit tests (`test_df_live_05_run_eval_keyboard_interrupt_saves_partial_report`, `test_cli_eval_keyboard_interrupt_exits_130`).
4. [LOW] Vacuous truth in `cmd_eval` when `repeat=0` because `summary` is empty: Fixed test-first (`test_cli_eval_repeat_zero_returns_exit_1`) with `bool(summary) and all(...)`.

Gate: `python3 scripts/sdlc_check.py` exited 0 (350 passed, 7 deselected).

## DF-LIVE-06 scenario acceptance and patch-scope enforcement — 2026-10-04

Independent reviewer: fresh stateless research subagent given the spec, plan and diff. Report: “NO FINDINGS.” Checked `target_files` and `protected_paths` declarations on all four evaluation scenarios (`primes`, `calculator`, `textutils`, `csvparse`), propagation to `TaskSpec` in `run_scenario`, patch-scope rejection for out-of-scope files (`reason: out_of_scope_patch`), strengthened test suites for boundary and negative cases, zero cloud tokens, and regression tests. Gate: `python3 scripts/sdlc_check.py` exited 0 (357 passed, 7 deselected).

## Phase 22 / Adversarial follow-up P1 (strict audit schema) & P2 (host isolation reconciliation) — 2026-10-04

Independent reviewer: fresh stateless research subagent (`827f7b14-b74d-4782-b537-a3d03c21a06d`) given the spec, plan and diff. Three findings (1 MEDIUM, 2 LOW), all fixed test-first:
1. [MEDIUM] `_parse_response` allowed missing `severity`, `category`, and `details` on finding items, and allowed empty string `summary`: Fixed test-first (`test_p1_rejects_finding_missing_severity`, `test_p1_rejects_finding_missing_category`, `test_p1_rejects_finding_missing_details`, `test_p1_rejects_empty_root_summary`, `test_p1_rejects_empty_finding_summary`) by strictly checking non-empty `summary` and all 4 required fields on each finding item.
2. [LOW] `test_r1_hostile_severity_is_allowlisted_at_parse_time` passed vacuously due to missing `passed` field: Fixed by providing a complete valid schema with hostile severity, confirming `_parse_response` rejects invalid severity with a schema `WARN` finding.
3. [LOW] `test_p1_rejects_finding_missing_required_fields_or_invalid_severity` omitted assertions for missing `severity`, `category`, or `details`: Fixed by adding explicit unit tests covering all required finding fields.

Scope:
- P1: Strict schema validation in `AdversarialAuditor._parse_response` (`dark_factory/verification/adversarial.py`) and regression tests in `tests/test_adversarial.py`. Validates `passed: bool`, non-empty `summary: str`, `findings: list[dict]`, requiring non-empty `summary`, valid `severity` (`INFO`, `WARN`, `CRITICAL`), and string `category`/`details` in each finding. Malformed outputs yield an unsuccessful report (`passed=False`) with an explanatory `WARN` finding in category `regression`.
- P2: Reconciled user-facing sandbox claims in `docs/architecture.md`, `README.md`, and `docs/index.md` with `spec.md` isolation limits. Recorded synthetic outside-worktree write reproduction as evidence: `GitWorktreeSandbox.execute` runs commands directly on the host using the sanitized environment, and can write outside its worktree if not constrained by OS permissions. Process-level sandboxing remains tracked in `plan.md` §10.5.

Gate: `python3 scripts/sdlc_check.py` exited 0 (368 passed, 7 deselected).

## Phase 23 / DF-LIVE-08 opening file block indentation tolerance — 2026-10-04

Independent reviewer: fresh stateless research subagent (`d8e607b9-9ab0-4dd6-a1df-420fab32677e`) given the spec, plan and diff. Report: “NO FINDINGS.”

Checked:
1. `_FILE_OPEN_RE = re.compile(r"^ {0,3}(`{3,})file:(.*)$")` in `dark_factory/harness/local_coder.py:17` allows 0 to 3 leading spaces, matching CommonMark fenced code block indentation specifications and resolving tokenization artifacts (e.g. leading space token emitted by Mistral-7B after `[/INST]`).
2. Indented code blocks with 4 or more leading spaces are rejected, correctly distinguishing CommonMark indented blocks from fenced file blocks (verified in `tests/test_harness.py`).
3. Non-capturing indentation (` {0,3}`) preserves `opener.group(1)` as backticks and `opener.group(2)` as file path, keeping `outer_len` and nested code fence tracking intact.
4. Symmetry with `_FENCE_RE = re.compile(r"^ {0,3}(`{3,})(.*)$")` is established.
5. All docs (`spec.md` ↔ `docs/sdlc/spec.md`), `CHANGELOG.md`, and `plan.md` synchronized.

Gate: `python3 scripts/sdlc_check.py` exited 0 (370 passed, 7 deselected).




## Backlog documentation realignment — 2026-10-04

Scope: this session's documentation edits only (`plan.md`, intent/spec and mirrors, this record). Existing source, tests, changelog and historical review changes were preserved and are not reviewed by this entry.

Reconciled delivered DF-LIVE work, historical benchmark cohorts, review gaps, upstream Prism development state, existing eval/report contracts and intent progress. Active follow-ups have acceptance procedures and authorization boundaries; release remains on hold. No invariant or public API change.

Verification: `python3 scripts/sdlc_check.py` exited 0 (370 passed, 7 local-engine tests deselected; lint, format, strict docs and changelog PASS). `pytest tests/test_docs_alignment.py -q`: 5 passed. `git diff --check` clean; edited intent/spec/review mirrors are byte-identical. Independent review: not performed; remains open as plan item 24.3. Operator deferred live Ollama work ("testy na zywej ollamie zrobimy potem"). A read-only `/api/tags` inventory was retrieved before this instruction; no generation calls, live-model tests or benchmark campaigns ran. Author inspection is not independent review.

Next step: retain the documentation-review checkbox open; resume fresh local review when local-model work is resumed. Product post-review fix checks remain separately tracked as BL-01. No commits, pushes or releases.

## Live Ollama existing test suite — 2026-10-04

Operator resumed tests with "teraz jedz z testami". Existing `pytest tests/ -m local_engine -vv -rA` suite: **6 passed, 1 skipped, 370 deselected in 82.86s**, exit 0. Six cases used local Ollama `qwen2.5-coder:14b`; Prism-only residency test skipped because Prism was offline. Initial restricted-sandbox invocation skipped all seven due to blocked sockets; its output is not live-model validation. Authorized outside-sandbox execution supplied the actual result.

Evidence: `.factory/live-ollama-20261004T184244Z/` contains protocol, `pytest-live.log`, `junit-live.xml`, `inspection.json` and retained fixture artifacts. Tests covered primes, two-file calculator, realistic slugify bugfix (pytest + ruff), CLI run/review, CSV self-healing and eval reporting. CSV required 2 repairs; all other runs 0. All six patch hashes, manifests, transcripts, telemetry and zero cloud cost checked. Five E2E fixture repositories have clean tracked trees, untracked `__pycache__` only and one primary worktree each; eval temporary source was removed. Test review/commits applied only to disposable fixtures. Product source/tests were not edited.

Full deterministic gate `python3 scripts/sdlc_check.py` exited 0: 370 passed, 7 local-engine deselected; lint, format, strict docs and changelog PASS. This is test evidence, not independent review or completion of BL-02–05 campaigns. Documentation review 24.3 and product re-reviews BL-01 remain open. No product commits, pushes, releases or inference-service restart.
