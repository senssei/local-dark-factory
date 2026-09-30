---
name: sdlc
description: Entry point for the project's AI-native SDLC (intent, spec, plan, test, code, review). Use when starting any non-trivial feature, bugfix or refactor, when resuming work after /clear or a harness switch, or when the user asks "where are we" or "what's next".
---

# SDLC router

Work moves through **intent -> spec -> plan -> test -> code -> review**. The state is in committed files (`intent.md`,
`spec.md`, `plan.md`, `REVIEW.md`) and in git, never in the chat. This skill finds the current stage and hands over. It does no
engineering itself.

## 1. Read the state

```bash
git status --short; git log --oneline <base>..HEAD              # <base> is `base` in sdlc.toml (default main)
grep -n "^## Phase\|^Status:\|^- \[ \]" plan.md               # phases, in-flight notes, open items
git diff --stat $(git merge-base <base> HEAD)                   # what already changed
python3 scripts/sdlc_check.py                                   # is the tree green right now?
```

When you are on the base branch itself, the range and the diff above are empty; that is expected (work happens on a branch or in the
working tree, and the runner then compares only uncommitted changes).

Read the phase in `plan.md` the change belongs to, including its `Status:` line (the handoff note), and the parts of `spec.md`
it touches. If `intent.md`, `spec.md` or `plan.md` do not exist or are still the untouched template, the project is at stage 1.

## 2. Pick the stage

| What you find | Stage | Skill |
|---|---|---|
| The request is not in `plan.md`, or the spec does not describe the behavior, or the operator has not approved the plan | 1 to 3 | `sdlc-plan` |
| An approved, unticked item; no failing test for it yet, or code half-written | 4 and 5 | `sdlc-implement` |
| Item's code is done and green, but there was no independent review yet | 6 | `sdlc-review` |
| Reviewed, gate green, the operator wants to commit, open a PR or release | ship | `sdlc-release` (see below) |
| All items of the change are ticked and shipped | done | tell the user |

**Shortcuts** (say which you take): a **bug fix** starts at stage 4 (failing test first; `spec.md` first if the intended behavior was
undefined). A **trivial change** (typo, comment, docs wording) skips stages 1 to 4: edit, run the gate, done.

If the artifacts and git disagree (an item ticked but the diff is empty, code with no plan item), trust git, tell the user, and fix
the artifact. If several plan items are in flight and it is not obvious which one the user means, ask.

## 3. Hand over

Say in one line which stage you enter and why, then invoke the skill. Exception: `sdlc-release` cannot be invoked by the agent in
Claude Code (`disable-model-invocation`), so ask the user to run `/sdlc-release`; in other harnesses read and follow it. Before ending a session mid-change, update the phase's
`Status:` line in `plan.md` (what is done, what is next) and keep the checkboxes true. The next agent, in any harness, starts with
`/sdlc` (Claude Code) or "use the sdlc skill" (Codex, Gemini CLI, Copilot, Cursor, MiniMax Code) and needs nothing else from you.

## Rules

- A stage is finished only when its artifact exists on disk (`AGENTS.md`, process table). Do not skip or reorder stages.
- Never tick a plan box before the gate (`python3 scripts/sdlc_check.py`) exited 0 in this session.
- The operator gates in `AGENTS.md` always apply.
