# Agent Instructions (`AGENTS.md`)

This repository (**local-dark-factory**) implements the **Sovereign Dark Factory**: an autonomous, local-first software factory orchestrator that coordinates local coding agents, executes deterministic verification gates, preserves patches, and provides human-in-the-loop review.

---

## 🚀 Core Guideline: Zero Cloud Tokens

All agents and subagents operating within this repository must adhere to the local-first mandate:
1. **Never import or call external cloud LLM APIs** (OpenAI, Anthropic, Google Cloud API keys).
2. **Utilize our local inference engines**:
   - `local-coder`: Unified multi-engine router.
   - `ollama`: Direct Ollama backend (`qwen2.5-coder:14b`, `llama3.1:8b` at `http://localhost:11434`).
   - `prism`: Prism CUDA accelerator (`http://127.0.0.1:5272/v1`).
3. All code generation, unit test authoring, and refactoring within factory tasks must run through `LocalCoderHarness` or local endpoints with zero cloud token cost.

---

## 🛠 Development & Code Standards

1. **Language & Runtime**: Python 3.11+ with strict type hinting (`from __future__ import annotations`).
2. **Data Contracts**: Dataclasses with immutable or well-defined fields.
3. **Execution Safety**: Commands must be passed as `list[str]` (argv), never raw unescaped shell strings.
4. **Idempotency**: All cleanup actions (`sandbox.destroy()`, rollback routines) must be completely idempotent.
5. **Testing**: Write comprehensive unit tests for all domain logic, sandbox drivers, and verification runners in `tests/`.

---

## 🔍 Diagnostic & Status Commands

```bash
# Check local models & GPU connectivity:
dark-factory doctor

# Inspect Ollama running tags:
curl -s http://localhost:11434/api/tags

# Run test suite:
pytest tests/ -v
```
