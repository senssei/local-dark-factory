# Changelog

All notable changes to this project are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [SemVer](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-09-20

First public release of **Sovereign Dark Factory** (`local-dark-factory`).

### Added
- **Sandbox Fabric (`dark_factory.sandbox`)**:
  - `GitWorktreeSandbox`: Lightweight, isolated execution environment created via detached git worktrees (`git worktree add --detach`).
  - Path-traversal security guards to prevent modifications outside the worktree.
  - Verification gate restoration mechanism to prevent agents from tampering with test gates.
  - Subprocess execution with strict argv commands, hard timeouts, and idempotent cleanup (`sandbox.destroy()`).
- **Local Inference Harness (`dark_factory.harness`)**:
  - `LocalCoderHarness`: Multi-engine router supporting Ollama (`qwen2.5-coder:14b`), Prism CUDA (`http://127.0.0.1:5272/v1`), and Microsoft Foundry Local.
  - Zero cloud tokens guarantee: strictly local inference with $0.00 cloud API costs.
  - AST-aware patch parsing (`parse_file_blocks`) and generation telemetry collection (tokens, duration, tokens/sec).
- **Deterministic Verification & Self-Healing (`dark_factory.verification`)**:
  - `VerificationRunner`: Authoritative gatekeeper executing deterministic verification scripts (`build.sh`, `test.sh`, `pytest`).
  - Zero-gate safety guard: fails runs where no verification gates are discovered unless explicitly allowed.
  - Self-healing loop: feeds error traces and compiler outputs back into the local model for up to `N` iterative retry attempts.
  - Cumulative telemetry aggregation across multiple retry iterations.
- **Durable Workflow Orchestrator (`dark_factory.orchestrator`)**:
  - `DurableEngine`: SQLite-backed state machine tracking task lifecycle (`PENDING`, `RUNNING`, `VERIFYING`, `HEALING`, `AWAITING_REVIEW`, `APPLIED`, `REJECTED`, `FAILED`).
  - Transactional state transitions and resilient crash recovery (`dark-factory recover`).
  - Human-in-the-Loop review gate with SHA-256 patch verification.
- **Evidence Locker (`dark_factory.storage`)**:
  - `EvidenceLocker`: Structured persistence for unified git diffs (`diff.patch`), run manifests (`manifest.json`), verification logs, and telemetry summaries.
- **CLI & Operator Controls (`dark-factory` / `local-dark-factory`)**:
  - `dark-factory doctor`: Inspects Ollama, Prism, GPU VRAM, git binary, and sandbox fabric.
  - `dark-factory run`: Submits an autonomous coding task with optional timeout and gate overrides.
  - `dark-factory list`: Lists all task runs and their execution states.
  - `dark-factory describe <RUN_ID>`: Prints task manifest, conditions, gate results, and unified diff.
  - `dark-factory review <RUN_ID> --approve [--branch <NAME>]`: Applies verified patch to target branch.
  - `dark-factory review <RUN_ID> --reject [--note <REASON>]`: Rejects and archives run.
  - `dark-factory recover`: Resumes interrupted tasks after system restart.
- **Documentation & CI/CD**:
  - MkDocs Material documentation site with API references, architectural diagrams, and SDLC guides.
  - GitHub Actions CI pipeline testing across Python 3.11 and 3.12 with package wheel smoke-testing.
  - Native GitHub Pages deployment pipeline.
  - OIDC Trusted Publishing workflow for TestPyPI and PyPI.

[Unreleased]: https://github.com/senssei/local-dark-factory/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/senssei/local-dark-factory/releases/tag/v0.1.0
