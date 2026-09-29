"""Deterministic verification runner for Sovereign Dark Factory."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from dark_factory.domain.errors import RunTimeoutError
from dark_factory.domain.types import StepExecution, VerificationStep
from dark_factory.sandbox.base import Sandbox

# Gate definitions and test-runner configuration an agent must not be able to weaken (e.g. via
# `[tool.pytest.ini_options] addopts = "--deselect ..."` or a root `conftest.py` that skips tests).
_DEFAULT_PROTECTED_PATHS = (
    "tests",
    "test",
    "test.sh",
    "pytest.ini",
    "tox.ini",
    "pyproject.toml",
    "setup.cfg",
    ".coveragerc",
)
# Files that alter test-runner / interpreter behaviour at any directory depth (git glob pathspecs).
_DEFAULT_PROTECTED_ANYWHERE = ("conftest.py", "sitecustomize.py", "usercustomize.py")

# Runner/interpreter binaries: never themselves a path to protect.
_RUNNER_LITERALS = frozenset({"python", "python3", "pytest", "sh", "bash"})
# Linters/formatters/type-checkers: their argv names the file(s) the agent must be free to edit (the lint
# *target*), not a test/gate file, so a step invoking one of these contributes nothing to the
# argv-derived protected-path set (the fixed `_DEFAULT_PROTECTED_PATHS` baseline still applies).
_LINTER_LIKE_TOOLS = frozenset({"ruff", "flake8", "pylint", "mypy", "pyright", "black", "isort"})


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
        """Infer default protected gate files and directories from configured steps.

        A step that invokes a linter/formatter/type-checker (`ruff`, `mypy`, ...) names its lint
        *targets* in argv, not test/gate files — those are exactly the files the agent is expected to
        edit, so such a step contributes nothing to the detected set (the fixed `_DEFAULT_PROTECTED_PATHS`
        baseline still applies). Without this, a gate like `ruff check <file>` would get `<file>` silently
        reverted to baseline before every verification pass, making the task unsolvable whenever the lint
        target is the very file the agent must fix.
        """
        paths = set()
        for step in self.steps:
            if any(Path(arg.removeprefix("./")).stem in _LINTER_LIKE_TOOLS for arg in step.argv):
                continue
            for arg in step.argv:
                arg_clean = arg.removeprefix("./")
                if (
                    arg_clean
                    and not arg_clean.startswith("-")
                    and arg_clean not in _RUNNER_LITERALS
                    and not arg_clean.endswith(".exe")
                ):
                    paths.add(arg_clean)
        paths.update(_DEFAULT_PROTECTED_PATHS)
        paths.update(f":(glob)**/{name}" for name in _DEFAULT_PROTECTED_ANYWHERE)
        return sorted(paths)

    def run(self, sandbox: Sandbox, deadline: float | None = None) -> VerificationOutcome:
        """Run all verification steps. Stops on the first failing mandatory step.

        `deadline` is a `time.monotonic()` instant; each gate's timeout is clamped to the time remaining.
        """
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
            # Spec §202: deadline is enforced at every phase boundary. When it has already
            # passed, the next gate must NOT be launched; we surface the partial executions
            # so the engine can adopt a TIMED_OUT outcome without spawning further sub-processes.
            if deadline is not None and time.monotonic() >= deadline:
                raise RunTimeoutError(
                    "Verification deadline exceeded before gate execution.",
                    executions=executions,
                )
            timeout = step.timeout_sec
            if deadline is not None:
                remaining = int(deadline - time.monotonic())
                if remaining <= 0:
                    # Defensive: should be unreachable thanks to the short-circuit above.
                    raise RunTimeoutError(
                        "Verification deadline exceeded during gate scheduling.",
                        executions=executions,
                    )
                timeout = min(timeout, remaining)
            exec_res = sandbox.execute(
                argv=step.argv,
                timeout=timeout,
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
