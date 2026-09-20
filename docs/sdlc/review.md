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
