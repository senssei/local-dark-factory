# Sovereign Dark Factory (`local-dark-factory`)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-teal.svg)](https://senssei.github.io/local-dark-factory/)
[![CI](https://github.com/senssei/local-dark-factory/actions/workflows/ci.yml/badge.svg)](https://github.com/senssei/local-dark-factory/actions/workflows/ci.yml)
[![Zero Cloud Tokens](https://img.shields.io/badge/Cloud%20Tokens-%240.00-success.svg)](intent.md)
[![Hardware](https://img.shields.io/badge/Hardware-NVIDIA%20RTX%205070-76b900.svg)](intent.md)

A local-first, zero-cloud-token **AI Software Factory** that coordinates coding agents in fast, isolated git worktrees, enforces deterministic verification gates, preserves patches and execution evidence, and integrates human-in-the-loop governance.

> *"Make sure you own your AI. AI in the cloud is not aligned with you; it’s aligned with the company that owns it."*

---

## 📖 AI-Native SDLC Architecture

This project follows the **[AI-Native SDLC Playbook](https://claude.com/blog/the-ai-native-sdlc-playbook)**:

| Artifact | Purpose | Status |
|---|---|---|
| [**`intent.md`**](intent.md) | The Planning Artifact: Problem statement, vision, constraints, and success criteria. | ✅ Established |
| [**`spec.md`**](spec.md) | Technical Specification: Architecture, data contracts, and component interfaces. | ✅ Established |
| [**`CLAUDE.md`**](CLAUDE.md) | Project Operating Manual: Build/test commands, non-negotiable rules, and architectural guidelines. | ✅ Established |
| [**`AGENTS.md`**](AGENTS.md) | Agent Instructions: Guidelines for local inference skills (`05-local-coders`) and code standards. | ✅ Established |
| [**`plan.md`**](plan.md) | Implementation Roadmap: Phased execution plan from domain contracts to E2E CLI. | ✅ Established |
| [**`REVIEW.md`**](REVIEW.md) | Governance & Review Policy: Human-in-the-loop (HITL) criteria and operator commands. | ✅ Established |

---

## 🔗 The Local Stack Integration

Unlike existing cloud-bound prototypes, the Sovereign Dark Factory runs entirely on your workstation without cloud dependencies:

```text
Task Submission (CLI / Trigger)
       │
       ▼
Durable SQLite Workflow Engine (.factory/factory.db)
       │
       ▼
Disposable Git Worktree Sandbox (<100ms startup)
       │
       ▼
Local Agent Harness (05-local-coders)
       ├── Ollama (:11434): qwen2.5-coder:14b / 7b
       └── Prism CUDA (:5272): phi4-mini / ONNX GenAI (03-foundy-local)
       │
       ▼
Deterministic Verification Gates (test.sh / pytest / cargo / npm)
       │
       ├──[Failed]──► AST Self-Healing Loop (max N retries)
       │
       └──[Passed]──► Evidence Locker (.factory/runs/<RUN_ID>/diff.patch)
                            │
                            ▼
               Human-in-the-Loop Review Gate (dark-factory review --approve)
```

---

## 🚀 Quick Start (Development)

```bash
# 1. Health check local engines & GPU
python3 -m dark_factory.cli doctor

# 2. Run unit tests
pytest tests/ -v

# 3. Submit a dark factory task
python3 -m dark_factory.cli run \
  --repo /path/to/repo \
  --task "Implement thread-safe token bucket limiter" \
  --gates default
```
