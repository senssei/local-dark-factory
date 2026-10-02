"""Active Adversarial Test Mutator for Sovereign Dark Factory."""

from __future__ import annotations

import ast
import logging

from dark_factory.harness.llm_text import cap_text, extract_code_block, fence
from dark_factory.harness.local_coder import LocalCoderHarness

logger = logging.getLogger(__name__)

MAX_PROBE_PATCH_CHARS = 12000  # about 4000 estimated tokens; keeps the prompt inside the default window

_MUTATOR_SYSTEM_PROMPT = """You are a Hostile Adversarial QA Engineer / Red Team tester in the Sovereign Dark Factory.
Your job is to synthesize executable Python pytest unit tests that actively stress-test and probe a proposed code patch.
Your goal is to break the implementation by finding:
1. Boundary & extreme value flaws (negative numbers, 0, float inf/nan, empty collections, very large inputs).
2. Missing edge cases and unhandled exceptions (null/None checks, division by zero, invalid types).
3. Anti-cheating & shortcut violations: If the code uses hardcoded outputs or checks specifically for test values, write assertions with different parameters that violate the shortcut.
4. Interface contract & invariant violations.

Format Rules:
- Output ONLY valid, executable Python code suitable for running via `pytest`.
- You may wrap your code in ```python ... ``` fences.
- Import standard libraries and target modules directly.
- Define test functions starting with `test_*`.
- Use standard `assert` statements or `pytest.raises(...)`.
- Do not output any conversational prose, explanations, or markdown text outside the code block."""


class AdversarialMutator:
    """Synthesizes dynamic hostile unit tests to probe code patches in the sandbox."""

    def __init__(self, harness: LocalCoderHarness | None = None) -> None:
        self.harness = harness or LocalCoderHarness()

    def generate_probe(
        self,
        task_prompt: str,
        patch: str,
        context: str = "",
    ) -> str | None:
        """Generate Python pytest code to actively probe the modified code in patch.

        Returns valid Python code string if generation and AST validation succeed,
        or None if patch is empty or generation/syntax validation fails.
        """
        if not patch or not patch.strip():
            return None

        system_prompt = _MUTATOR_SYSTEM_PROMPT
        user_prompt = self._build_user_prompt(task_prompt, cap_text(patch, MAX_PROBE_PATCH_CHARS)[0], context)

        try:
            raw_text, _telemetry = self.harness._call_model(system_prompt, user_prompt)
            return self._parse_and_validate(raw_text)
        except Exception as exc:
            logger.warning("Adversarial mutator call failed: %s", exc)
            return None

    def _build_user_prompt(self, task_prompt: str, patch: str, context: str = "") -> str:
        ctx_block = f"\nREPOSITORY CONTEXT:\n{context}\n" if context.strip() else ""
        return (
            f"TASK SPECIFICATION:\n{task_prompt}\n"
            f"{ctx_block}\n"
            f"PROPOSED UNIFIED DIFF:\n{fence(patch, 'diff')}\n\n"
            "Generate hostile pytest unit tests probing the code changes above. Output executable Python code only."
        )

    def _parse_and_validate(self, raw_text: str) -> str | None:
        """Extract Python code block and validate syntax with ast.parse."""
        cleaned = extract_code_block(raw_text, "python")

        if not cleaned:
            return None

        try:
            ast.parse(cleaned)
            return cleaned
        except SyntaxError as exc:
            logger.warning("Adversarial mutator generated invalid Python syntax: %s", exc)
            return None
