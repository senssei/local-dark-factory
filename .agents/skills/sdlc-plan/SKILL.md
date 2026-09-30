---
name: sdlc-plan
description: Stages 1 to 3 of the SDLC. Check the change against intent.md, write the new behavior into spec.md, and add plan.md items that name their files and tests, then get the operator's approval before any code. Use when a feature, bugfix or refactor is requested and the spec or an approved plan item does not exist yet.
---

# Stages 1 to 3: intent, spec, plan

Goal: agree on what "done" means before touching code. The output is edits to `intent.md` (only if needed), `spec.md` and
`plan.md`. Do not edit source code or tests in this phase.

## Steps

1. **Restate the request** in one or two sentences. If it is ambiguous in a way that changes the design, ask one focused question
   now. Do not guess, and do not ask what the code can answer. Questions that remain open go into the approval request (step 7).
   If `intent.md` is still the untouched template, drafting it is the first step: ask the operator for the problem, constraints and
   non-goals, do not invent them, and keep the file marked as a draft until it is approved.
2. **Explore.** Read the code that owns the behavior, its tests, the docs that describe it, the relevant part of `spec.md`, and the
   changelog if the project keeps one. Read files, do not skim names. For a wide search use a read-only exploration subagent if the
   harness has one.
3. **Stage 1, intent.** Does the change fit `intent.md` (problem, outcome, constraints, non-goals)? If it contradicts it, stop:
   propose the edit to `intent.md` and get the operator's approval before continuing. Changing an invariant in `spec.md` is the
   same kind of change.
4. **Stage 2, spec.** Write the behavior into `spec.md`: what must stay true, the failure modes and their status or exit code, the
   configuration it adds, and which normative doc changes. Planned behavior goes under "Planned behavior" until it is built. Prefer
   pointing at a normative doc over repeating its tables.
5. **Stage 3, plan.** Add `- [ ]` items to `plan.md` under a phase (create the phase if needed). One item is one commit-sized
   step. Each names the files it touches and the test that proves it. Add items for docs and the changelog when the change is
   user-visible. Put risks and open questions in the phase, especially what a test cannot cover.
6. **Check the project rules** in `AGENTS.md` (section "Project rules") against the plan and against the invariants in `spec.md`.
7. **Present the changes** to the artifacts (`git diff` for edited files, `git status` for new ones; not the whole exploration) as an
   approval request that lists the open questions, and ask for approval. Do not start implementing in the same turn.
8. On approval, record it on disk: if `intent.md` was changed or is still a draft, set its status line to
   `> **Status: approved by the operator, <date>.**`, and add `Status: approved by the operator, not started.` under the phase
   heading in `plan.md`.

## Exit criterion

`spec.md` describes the behavior, every plan item names its files and its test, and the operator approved. If the scope changes,
edit the artifacts; do not just remember it.
