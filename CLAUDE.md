@AGENTS.md

## Claude Code specifics

- Start with `/sdlc`: it reads `plan.md` and the git state and tells you which stage you are in. The phase skills are
  `/sdlc-plan`, `/sdlc-implement`, `/sdlc-review` and `/sdlc-release`. They live in `.agents/skills/`; `.claude/skills` is a symlink.
- For `sdlc-review`, the independent reviewer that `AGENTS.md` requires is the Agent tool with `general-purpose`.
- `sdlc-release` is user-invoked only (`/sdlc-release`); ask the user to run it when the change is ready to ship.
