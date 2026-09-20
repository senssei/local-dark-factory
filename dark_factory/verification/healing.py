"""Self-healing loop that feeds compiler and test errors back into the local model."""

from __future__ import annotations

from dark_factory.domain.types import ModelTelemetry, StepExecution
from dark_factory.harness.base import AgentHarness
from dark_factory.sandbox.base import Sandbox
from dark_factory.verification.runner import VerificationOutcome, VerificationRunner


class SelfHealingLoop:
    """Orchestrates the agent-verification feedback loop up to max_retries."""

    def __init__(self, max_retries: int = 3) -> None:
        self.max_retries = max_retries

    def run_loop(
        self,
        sandbox: Sandbox,
        harness: AgentHarness,
        initial_prompt: str,
        verification_runner: VerificationRunner,
        target_files: list[str] | None = None,
    ) -> tuple[bool, int, list[StepExecution], ModelTelemetry | None]:
        """Run initial generation and up to max_retries self-healing attempts.

        Returns:
            (passed, total_healing_attempts, all_executions, aggregated_telemetry)
        """
        all_executions: list[StepExecution] = []
        healing_attempts = 0
        current_prompt = initial_prompt
        last_telemetry: ModelTelemetry | None = None

        while True:
            # 1. Run Harness
            harness_result = harness.execute_task(
                sandbox=sandbox,
                task_prompt=current_prompt,
                target_files=target_files,
            )
            if harness_result.telemetry:
                last_telemetry = harness_result.telemetry

            if not harness_result.success:
                # Harness failed to generate or apply changes
                return False, healing_attempts, all_executions, last_telemetry

            # 2. Run Verification
            outcome: VerificationOutcome = verification_runner.run(sandbox)
            all_executions.extend(outcome.executions)

            # If all verification gates passed, we succeed!
            if outcome.passed:
                return True, healing_attempts, all_executions, last_telemetry

            # 3. Check retry budget
            if healing_attempts >= self.max_retries:
                # Exceeded retry budget
                return False, healing_attempts, all_executions, last_telemetry

            healing_attempts += 1

            # 4. Construct repair prompt with error trace
            error_trace = outcome.error_summary
            current_prompt = (
                f"REPAIR ATTEMPT #{healing_attempts}:\n"
                f"Your previous changes failed automated deterministic verification.\n"
                f"{error_trace}\n\n"
                "Please analyze the errors above and generate the corrected full file contents.\n"
                "Remember to format all updated files in ```file:<path> ... ``` blocks."
            )
