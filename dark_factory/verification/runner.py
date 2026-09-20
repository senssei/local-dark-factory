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
    tampered_paths: list[str] = field(default_factory=list)

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

    def __init__(
        self,
        steps: list[VerificationStep],
        allow_no_verify: bool = False,
        protected_paths: list[str] | None = None,
        allow_gate_edits: bool = False,
        base_rev: str = "HEAD",
    ) -> None:
        self.steps = steps
        self.allow_no_verify = allow_no_verify
        self.protected_paths = protected_paths or []
        self.allow_gate_edits = allow_gate_edits
        self.base_rev = base_rev

    def detect_default_gate_paths(self) -> list[str]:
        """Infer default protected gate files and directories from configured steps."""
        paths = set()
        for step in self.steps:
            for arg in step.argv:
                arg_clean = arg.lstrip("./")
                if (
                    arg_clean
                    and not arg_clean.startswith("-")
                    and arg_clean not in {"python", "python3", "pytest", "sh", "bash"}
                    and not arg_clean.endswith(".exe")
                ):
                    paths.add(arg_clean)
        paths.update(["tests", "test", "test.sh", "pytest.ini", "tox.ini"])
        return sorted(paths)

    def run(self, sandbox: Sandbox) -> VerificationOutcome:
        """Run all verification steps. Stops on the first failing mandatory step."""
        if not self.steps:
            if self.allow_no_verify:
                return VerificationOutcome(passed=True, executions=[])
            return VerificationOutcome(
                passed=False,
                executions=[],
                failed_step=StepExecution(
                    step_id="verification_gate_check",
                    exit_code=1,
                    stdout="",
                    stderr=(
                        "Zero verification gates configured. A dark factory run requires deterministic "
                        "verification gates (or explicit --no-verify)."
                    ),
                    duration_sec=0.0,
                ),
            )

        # Gate protection: restore baseline test/gate files before running verification
        restored: list[str] = []
        if not self.allow_gate_edits and hasattr(sandbox, "restore_paths"):
            paths_to_protect = self.protected_paths or self.detect_default_gate_paths()
            restored = sandbox.restore_paths(paths_to_protect, rev=self.base_rev)

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
                    tampered_paths=restored,
                )

        return VerificationOutcome(
            passed=True,
            executions=executions,
            tampered_paths=restored,
        )
