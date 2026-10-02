"""Self-healing loop that feeds compiler and test errors back into the local model."""

from __future__ import annotations

import re
import time
from collections.abc import Callable

from dark_factory.domain.errors import RunTimeoutError
from dark_factory.domain.types import ModelTelemetry, RunStatus, StepExecution
from dark_factory.harness.base import AgentHarness
from dark_factory.harness.llm_text import cap_text
from dark_factory.sandbox.base import Sandbox
from dark_factory.verification.runner import VerificationOutcome, VerificationRunner

# Matches a volatile "N.NNs" duration substring (e.g. pytest's own "1 failed in 0.03s" footer). Two
# verification runs with the *same* real outcome can still differ here purely from wall-clock noise, so
# it must be normalized away before comparing "is this the same failure as last time".
MAX_ERROR_TRACE_CHARS = 6000  # about 2000 estimated tokens of gate output in a repair prompt
_DURATION_RE = re.compile(r"\d+\.\d+s\b")


def _normalize_for_signature(text: str) -> str:
    return _DURATION_RE.sub("<dur>", text)


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
        deadline: float | None = None,
    ) -> tuple[bool, int, list[StepExecution], ModelTelemetry | None, int]:
        """Run initial generation and up to max_retries self-healing attempts.

        `deadline` is a `time.monotonic()` instant checked at every phase boundary; when it has passed a
        `RunTimeoutError` carrying the partial results is raised.

        Returns:
            (passed, total_healing_attempts, all_executions, aggregated_telemetry, repeated_failure_streak)

        `repeated_failure_streak` counts consecutive verification failures with an identical outcome
        (same gate, exit code, stdout, stderr) ending at the return point — a model that keeps re-deriving
        the same wrong fix produces byte-identical verification failures attempt after attempt, which is a
        distinct failure mode from trying different (still wrong) approaches each time. It's 0 on success.
        """

        def check_deadline() -> None:
            if deadline is not None and time.monotonic() >= deadline:
                raise RunTimeoutError(
                    "Run deadline exceeded.",
                    executions=all_executions,
                    healing_attempts=healing_attempts,
                    telemetry=aggregated_telemetry,
                )

        all_executions: list[StepExecution] = []
        healing_attempts = 0
        current_prompt = initial_prompt
        aggregated_telemetry: ModelTelemetry | None = None
        last_failure_signature: tuple[str, int, str, str] | None = None
        repeated_failure_streak = 0

        while True:
            check_deadline()

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
                        num_ctx=t.num_ctx,
                    )
                else:
                    aggregated_telemetry.prompt_tokens += t.prompt_tokens
                    aggregated_telemetry.completion_tokens += t.completion_tokens
                    aggregated_telemetry.total_tokens += t.total_tokens
                    aggregated_telemetry.duration_sec = round(aggregated_telemetry.duration_sec + t.duration_sec, 3)
                    if t.num_ctx is not None:  # report the largest window any attempt used
                        aggregated_telemetry.num_ctx = max(aggregated_telemetry.num_ctx or 0, t.num_ctx)
                    if aggregated_telemetry.duration_sec > 0:
                        aggregated_telemetry.tokens_per_sec = round(
                            aggregated_telemetry.completion_tokens / aggregated_telemetry.duration_sec, 2
                        )

            # If harness failed to generate or parse blocks, treat as a healing retry
            if not harness_result.success:
                healing_attempts += 1
                error_msg = harness_result.error or "Model did not output any recognizable file blocks."
                if healing_attempts > self.max_retries:
                    # No gate ran, so keep the reason in the evidence instead of an unexplained FAILED. The
                    # last failure was the harness's, so an earlier gate-failure streak no longer applies.
                    all_executions.append(StepExecution("harness", 1, "", error_msg, 0.0))
                    return False, healing_attempts, all_executions, aggregated_telemetry, 0

                if status_callback:
                    status_callback(RunStatus.SELF_HEALING)

                current_prompt = (
                    f"ORIGINAL TASK:\n{initial_prompt}\n\n"
                    f"REPAIR ATTEMPT #{healing_attempts} OF {self.max_retries}:\n"
                    f"Your previous response failed to apply: {error_msg}\n\n"
                    "Please provide complete file contents formatted inside code blocks: ```file:<path> ... ```."
                )
                continue

            # 2. Run Verification
            check_deadline()
            if status_callback:
                status_callback(RunStatus.VERIFYING)

            outcome: VerificationOutcome = verification_runner.run(sandbox, deadline=deadline)
            all_executions.extend(outcome.executions)

            # If all verification gates passed, we succeed!
            if outcome.passed:
                return True, healing_attempts, all_executions, aggregated_telemetry, 0

            # Detect a model stuck re-deriving the same wrong fix: identical gate, exit code, and
            # stdout/stderr as the immediately preceding attempt (duration/timed_out excluded, and any
            # embedded "N.NNs" duration substring normalized away — e.g. pytest's own "1 failed in 0.03s"
            # footer — since those vary run to run even when the underlying code and outcome are unchanged).
            failed = outcome.failed_step
            failure_signature = (
                (
                    failed.step_id,
                    failed.exit_code,
                    _normalize_for_signature(failed.stdout),
                    _normalize_for_signature(failed.stderr),
                )
                if failed
                else None
            )
            if failure_signature is not None and failure_signature == last_failure_signature:
                repeated_failure_streak += 1
            else:
                repeated_failure_streak = 0
            last_failure_signature = failure_signature

            # 3. Check retry budget
            if healing_attempts >= self.max_retries:
                # Exceeded retry budget
                return False, healing_attempts, all_executions, aggregated_telemetry, repeated_failure_streak

            healing_attempts += 1
            if status_callback:
                status_callback(RunStatus.SELF_HEALING)

            # 4. Construct repair prompt with error trace AND original task retained
            # A full pytest dump can exceed the model's window; the head names the gate, the tail has the summary.
            error_trace, _ = cap_text(
                outcome.error_summary, MAX_ERROR_TRACE_CHARS, keep_tail=MAX_ERROR_TRACE_CHARS * 3 // 4
            )
            tamper_notice = ""
            if outcome.tampered_paths:
                tamper_notice = (
                    f"SECURITY NOTICE: Modifications to protected verification files "
                    f"({', '.join(outcome.tampered_paths)}) were detected and REVERTED to baseline.\n"
                    "You must NOT modify verification scripts or test files. Fix the application code instead!\n\n"
                )
            stuck_notice = ""
            if repeated_failure_streak >= 1:
                stuck_notice = (
                    "STUCK NOTICE: Your last fix resulted in the exact same test failure as the attempt "
                    "before it — your current approach is not working. Do not make a small tweak to the "
                    "same logic; use a fundamentally different algorithm or data structure to solve this "
                    "problem.\n\n"
                )

            current_prompt = (
                f"ORIGINAL TASK:\n{initial_prompt}\n\n"
                f"REPAIR ATTEMPT #{healing_attempts} OF {self.max_retries}:\n"
                f"Your previous changes failed automated deterministic verification.\n"
                f"{tamper_notice}"
                f"{stuck_notice}"
                f"{error_trace}\n\n"
                "Please analyze the errors in the context of the original task and generate the corrected full file contents.\n"
                "Remember to format all updated files in ```file:<path> ... ``` blocks."
            )
