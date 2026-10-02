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
