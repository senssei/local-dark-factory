"""Local Planner Engine for Sovereign Dark Factory."""

from __future__ import annotations

from uuid import uuid4

from dark_factory.domain.types import ExecutionPlan
from dark_factory.harness.llm_text import clean_text, extract_json_object, str_list, strip_think
from dark_factory.harness.local_coder import LocalCoderHarness

_PLANNER_SYSTEM_PROMPT = """You are the Lead Software Architect in the Sovereign Dark Factory.
Your job is to deeply reason about an incoming engineering task, analyze constraints and acceptance criteria, and produce a structured, minimal, and concrete execution plan before any code is written.

Format Rules:
You must respond ONLY with a valid JSON object matching this schema:
{
  "summary": "<Concise overview of the architectural solution>",
  "invariants": [
    "<Key invariant, constraint, or non-negotiable property 1>",
    "<Key invariant 2>"
  ],
  "steps": [
    "1. <Concrete atomic step 1>",
    "2. <Concrete atomic step 2>"
  ],
  "target_files": [
    "<path/to/file1.py>",
    "<path/to/file2.py>"
  ]
}

Focus on:
1. Identifying edge cases, state transitions, and boundary conditions.
2. Naming the exact target files that need creation or modification.
3. Keeping the implementation minimal without unrelated refactors.
Do not wrap your JSON in conversational prose or explanations. Output JSON only."""


class LocalPlanner:
    """Local reasoning agent that produces an ExecutionPlan prior to coding."""

    def __init__(self, harness: LocalCoderHarness | None = None) -> None:
        self.harness = harness or LocalCoderHarness()

    def generate_plan(
        self,
        task_prompt: str,
        context: str = "",
        plan_id: str = "",
    ) -> ExecutionPlan:
        """Execute reasoning prompt and parse the resulting ExecutionPlan."""
        plan_id = plan_id or f"plan-{uuid4().hex[:8]}"
        user_prompt = self._build_user_prompt(task_prompt, context)

        try:
            raw_text, _telemetry = self.harness._call_model(_PLANNER_SYSTEM_PROMPT, user_prompt)
            return self._parse_response(plan_id, raw_text)
        except Exception as exc:
            return ExecutionPlan(
                plan_id=plan_id,
                summary=f"Planner execution error: {exc}",
                invariants=[],
                steps=["1. Implement changes according to task prompt"],
                target_files=[],
                raw_plan=str(exc),
            )

    def _build_user_prompt(self, task_prompt: str, context: str) -> str:
        ctx_block = f"\nREPOSITORY CONTEXT:\n{context}\n" if context.strip() else ""
        return (
            f"TASK SPECIFICATION:\n{task_prompt}\n"
            f"{ctx_block}\n"
            "Analyze the task, discover architectural invariants, and produce the ExecutionPlan in JSON format."
        )

    def _parse_response(self, plan_id: str, raw_text: str) -> ExecutionPlan:
        """Parse raw model output into structured ExecutionPlan with graceful fallback."""
        try:
            data = extract_json_object(raw_text, keys=("summary", "steps", "invariants", "target_files"))
            summary = clean_text(str(data.get("summary", "Autonomous execution plan")))
            invariants = [clean_text(x) for x in str_list(data.get("invariants"))]
            steps = [clean_text(x) for x in str_list(data.get("steps"))]
            target_files = [clean_text(x) for x in str_list(data.get("target_files"))]

            return ExecutionPlan(
                plan_id=plan_id,
                summary=summary,
                invariants=invariants,
                steps=steps,
                target_files=target_files,
                raw_plan=raw_text,
            )
        except Exception:
            # Fallback for non-JSON or conversational prose output
            return ExecutionPlan(
                plan_id=plan_id,
                summary="Autonomous execution plan",
                invariants=[],
                steps=[s.strip() for s in clean_text(strip_think(raw_text)).splitlines() if s.strip()][:5]
                or ["1. Implement requested task"],
                target_files=[],
                raw_plan=raw_text,
            )
