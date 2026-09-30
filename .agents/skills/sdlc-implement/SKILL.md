---
name: sdlc-implement
description: Stages 4 and 5 of the SDLC. For each approved plan.md item, write a test and prove it fails for the right reason (sdlc_check.py --red), make the smallest change that turns it green, run the gate, and tick the box. Use when a plan item is approved, or when the user says to implement or continue implementing.
---

# Stages 4 and 5: test, code

Precondition: the item is in `plan.md`, `spec.md` describes its behavior, and the operator approved the plan. If not, go back to
`sdlc-plan`. A **bug fix** may start here: reproduce it with a failing test first, and update `spec.md` if the intended behavior
was undefined.

## Loop, once per plan item

1. Take the first unticked item. Put a one-line note in the phase's `Status:` in `plan.md` (what you are on).
2. **Stage 4, test first.** Write or extend a test that follows the testing rules in `AGENTS.md` (Project rules), if it has any. Import
   code that does not exist yet inside the test body, not at the top of the file: a module that fails to load counts as "not found",
   not red. Then prove it is red:
   ```bash
   python3 scripts/sdlc_check.py --red <test-id> [more ids...]
   ```
   The id format is whatever `[red].run` in `sdlc.toml` expects. It exits 0 only if every named test **fails** now, and prints one
   reason line per id. Read those lines: the reason must be the missing behavior (a wrong value, a missing function), not a typo in
   the test. It exits 1 for a test that already passes (proves nothing), that cannot be found, that times out, or whose command
   could not run or was killed. Fix the test until it is red for the right reason. If a new test passes at once, the behavior already
   exists or the test is too weak: strengthen it or drop it, and do not record it as red-proven.
3. **Stage 5, code.** Make the smallest change that passes. Match the surrounding style, naming and comment density. Do not
   refactor unrelated code and do not add dependencies the project rules forbid.
4. Run the tests you wrote, then the whole gate: `python3 scripts/sdlc_check.py`. Fix regressions before moving on.
5. **Tick the box** in `plan.md` only now, when the gate exited 0. Update `Status:` in one line.
6. Commit only if the operator asked. When they do: one logical change per commit, in the message style of `git log`.

## Traps

- The rules in `AGENTS.md` ("Project rules") are part of the spec. Read them before you write code, and test the ones your change
  can break.
- Do not weaken or delete a failing test to get green. If a test is wrong, say so and fix it in its own step.
- If the spec or plan turns out to be wrong, stop, fix the artifact, and tell the operator. Do not silently change scope.

## Exit criterion

All items of the change are ticked, the gate exited 0 in this session, and `git diff` contains nothing that is not in the plan.
Continue with `sdlc-review`.
