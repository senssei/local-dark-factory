"""Self-healing loop that feeds compiler and test errors back into the local model."""

from __future__ import annotations

from collections.abc import Callable

from dark_factory.domain.types import ModelTelemetry, RunStatus, StepExecution
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
        status_callback: Callable[[RunStatus], None] | None = None,
    ) -> tuple[bool, int, list[StepExecution], ModelTelemetry | None]:
        """Run initial generation and up to max_retries self-healing attempts.

        Returns:
            (passed, total_healing_attempts, all_executions, aggregated_telemetry)
        """
        all_executions: list[StepExecution] = []
        healing_attempts = 0
        current_prompt = initial_prompt
        aggregated_telemetry: ModelTelemetry | None = None

        while True:
            # 1. Run Harness
            harness_result = harness.execute_task(
                sandbox=sandbox,
                task_prompt=current_prompt,
                target_files=target_files,
            )

            # Aggregate telemetry across attempts
            if harness_result.telemetry:
                t = harness_result.telemetry
                if aggregated_telemetry is None:
                    aggregated_telemetry = ModelTelemetry(
                        engine=t.engine,
                        model_name=t.model_name,
                        prompt_tokens=t.prompt_tokens,
                        completion_tokens=t.completion_tokens,
                        total_tokens=t.total_tokens,
                        duration_sec=t.duration_sec,
                        tokens_per_sec=t.tokens_per_sec,
                        cost_usd=0.0,
                    )
                else:
                    aggregated_telemetry.prompt_tokens += t.prompt_tokens
                    aggregated_telemetry.completion_tokens += t.completion_tokens
                    aggregated_telemetry.total_tokens += t.total_tokens
                    aggregated_telemetry.duration_sec = round(aggregated_telemetry.duration_sec + t.duration_sec, 3)
                    if aggregated_telemetry.duration_sec > 0:
                        aggregated_telemetry.tokens_per_sec = round(
                            aggregated_telemetry.completion_tokens / aggregated_telemetry.duration_sec, 2
                        )

            # If harness failed to generate or parse blocks, treat as a healing retry
            if not harness_result.success:
                healing_attempts += 1
                if healing_attempts > self.max_retries:
                    return False, healing_attempts, all_executions, aggregated_telemetry

                if status_callback:
                    status_callback(RunStatus.SELF_HEALING)

                error_msg = harness_result.error or "Model did not output any recognizable file blocks."
                current_prompt = (
                    f"ORIGINAL TASK:\n{initial_prompt}\n\n"
                    f"REPAIR ATTEMPT #{healing_attempts} OF {self.max_retries}:\n"
                    f"Your previous response failed to apply: {error_msg}\n\n"
                    "Please provide complete file contents formatted inside code blocks: ```file:<path> ... ```."
                )
                continue

            # 2. Run Verification
            if status_callback:
                status_callback(RunStatus.VERIFYING)

            outcome: VerificationOutcome = verification_runner.run(sandbox)
            all_executions.extend(outcome.executions)

            # If all verification gates passed, we succeed!
            if outcome.passed:
                return True, healing_attempts, all_executions, aggregated_telemetry

            # 3. Check retry budget
            if healing_attempts >= self.max_retries:
                # Exceeded retry budget
                return False, healing_attempts, all_executions, aggregated_telemetry

            healing_attempts += 1
            if status_callback:
                status_callback(RunStatus.SELF_HEALING)

            # 4. Construct repair prompt with error trace AND original task retained
            error_trace = outcome.error_summary
            tamper_notice = ""
            if outcome.tampered_paths:
                tamper_notice = (
                    f"SECURITY NOTICE: Modifications to protected verification files "
                    f"({', '.join(outcome.tampered_paths)}) were detected and REVERTED to baseline.\n"
                    "You must NOT modify verification scripts or test files. Fix the application code instead!\n\n"
                )

            current_prompt = (
                f"ORIGINAL TASK:\n{initial_prompt}\n\n"
                f"REPAIR ATTEMPT #{healing_attempts} OF {self.max_retries}:\n"
                f"Your previous changes failed automated deterministic verification.\n"
                f"{tamper_notice}"
                f"{error_trace}\n\n"
                "Please analyze the errors in the context of the original task and generate the corrected full file contents.\n"
                "Remember to format all updated files in ```file:<path> ... ``` blocks."
            )
