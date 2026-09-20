"""Deterministic verification runner for Sovereign Dark Factory."""

from __future__ import annotations

from dataclasses import dataclass, field

from dark_factory.domain.types import StepExecution, VerificationStep
from dark_factory.sandbox.base import Sandbox


@dataclass
class VerificationOutcome:
    """Outcome of running a suite of verification gates."""

    passed: bool
    executions: list[StepExecution] = field(default_factory=list)
    failed_step: StepExecution | None = None

    @property
    def error_summary(self) -> str:
        if not self.failed_step:
            return ""
        stderr = self.failed_step.stderr.strip()
        stdout = self.failed_step.stdout.strip()
        msg = f"Gate '{self.failed_step.step_id}' failed with exit code {self.failed_step.exit_code}."
        if stderr:
            msg += f"\nSTDERR:\n{stderr}"
        elif stdout:
            msg += f"\nSTDOUT:\n{stdout}"
        return msg


class VerificationRunner:
    """Executes structured verification steps sequentially inside a sandbox."""

    def __init__(self, steps: list[VerificationStep]) -> None:
        self.steps = steps

    def run(self, sandbox: Sandbox) -> VerificationOutcome:
        """Run all verification steps. Stops on the first failing mandatory step."""
        executions = []

        for step in self.steps:
            exec_res = sandbox.execute(
                argv=step.argv,
                timeout=step.timeout_sec,
                step_id=step.id,
            )
            executions.append(exec_res)

            if step.mandatory and not exec_res.passed:
                return VerificationOutcome(
                    passed=False,
                    executions=executions,
                    failed_step=exec_res,
                )

        return VerificationOutcome(
            passed=True,
            executions=executions,
        )
