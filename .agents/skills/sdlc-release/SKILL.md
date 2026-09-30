---
name: sdlc-release
description: Ship step of the SDLC. Run the full gate, finish the changelog, draft the PR description and, only when explicitly asked, commit, push, open the PR or publish a release. Use when review is done and the user wants to commit, open a PR, or cut a release.
disable-model-invocation: true
---

# Ship

Precondition: independent review finished with no open finding. This step has outward-facing actions, so each one needs the
operator gate (`AGENTS.md`): it needs the operator's ask in this turn, an earlier "yes" does not carry over.

## 1. Gate (always)

```bash
python3 scripts/sdlc_check.py                   # add --base REF only when the base differs from `base` in sdlc.toml
```

Every check must be `PASS` (a `SKIP` is allowed when its tool is not installed; say so). On `FAIL`, fix the cause and rerun. Never
edit the runner or the config, or skip a check, to get green. Report the actual output.

## 2. Plan, changelog, version

- The plan items are ticked and the phase `Status:` line is current.
- If the project keeps a changelog, user-visible changes have an entry under its unreleased heading, written for users.
- A version bump and a dated changelog heading happen **only** when the operator is cutting a release. How the project releases
  is in `AGENTS.md` ("Project rules") or its own release doc.

## 3. PR description

Use the repository's pull request template if there is one (`.github/PULL_REQUEST_TEMPLATE.md`); otherwise: *What and why* from the
plan item and `spec.md`, *How it was tested* from the gate output and the tests added. Show it to the operator. Create the PR only
if asked.

## 4. Commit and push (only if asked)

Follow the commit and push rules in `AGENTS.md`. Never skip hooks. If commits are signed and the agent waits for a passphrase,
stop and ask the operator to unlock it; do not disable signing.

## 5. Publishing (only if asked, step by step)

Follow the project's release doc. Stop and ask before each of: pushing a tag, running a publish workflow, creating a release on the
hosting service. Issues and comments there are outward actions as well. Package registries are usually permanent: publish to a
test registry first when the project has one.

## Exit criterion

Gate green in this session, and every outward step the operator asked for is done and reported.
