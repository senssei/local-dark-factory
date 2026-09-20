"""Unit tests for VerificationRunner and SelfHealingLoop."""

from unittest.mock import MagicMock

from dark_factory.domain.types import ModelTelemetry, StepExecution, VerificationStep
from dark_factory.harness.base import AgentHarness, HarnessResult
from dark_factory.sandbox.base import Sandbox
from dark_factory.verification import SelfHealingLoop, VerificationRunner


class FakeSandbox(Sandbox):
    def __init__(self):
        self.exec_results = []
        self.current_index = 0

    def create(self, base_rev: str = "HEAD") -> None:
        pass

    def execute(self, argv, cwd=None, env=None, timeout=300, step_id="exec"):
        res = self.exec_results[self.current_index]
        self.current_index += 1
        return res

    def read_file(self, rel_path: str) -> bytes:
        return b""

    def write_file(self, rel_path: str, content: bytes) -> None:
        pass

    def get_diff(self) -> str:
        return ""

    def destroy(self) -> None:
        pass


def test_verification_runner_all_pass():
    sandbox = FakeSandbox()
    sandbox.exec_results = [
        StepExecution("build", 0, "Build OK", "", 1.0),
        StepExecution("test", 0, "Test OK", "", 2.0),
    ]

    steps = [
        VerificationStep("build", ["./build.sh"]),
        VerificationStep("test", ["./test.sh"]),
    ]
    runner = VerificationRunner(steps)
    outcome = runner.run(sandbox)

    assert outcome.passed
    assert len(outcome.executions) == 2
    assert outcome.failed_step is None


def test_verification_runner_mandatory_fail_stops_early():
    sandbox = FakeSandbox()
    sandbox.exec_results = [
        StepExecution("build", 1, "", "Syntax error", 0.5),
    ]

    steps = [
        VerificationStep("build", ["./build.sh"]),
        VerificationStep("test", ["./test.sh"]),
    ]
    runner = VerificationRunner(steps)
    outcome = runner.run(sandbox)

    assert not outcome.passed
    assert len(outcome.executions) == 1
    assert outcome.failed_step.step_id == "build"
    assert "Syntax error" in outcome.error_summary


def test_self_healing_heals_on_second_attempt():
    sandbox = FakeSandbox()
    # Attempt 0 fails, Attempt 1 passes
    sandbox.exec_results = [
        StepExecution("test", 1, "", "AssertionError: expected 4 got 5", 0.5),
        StepExecution("test", 0, "All tests passed", "", 0.5),
    ]

    mock_harness = MagicMock(spec=AgentHarness)
    mock_harness.execute_task.return_value = HarnessResult(
        success=True,
        modified_files=["calc.py"],
        telemetry=ModelTelemetry(engine="ollama", model_name="qwen2.5-coder:14b"),
    )

    runner = VerificationRunner([VerificationStep("test", ["pytest"])])
    healer = SelfHealingLoop(max_retries=2)

    passed, healing_attempts, executions, telemetry = healer.run_loop(
        sandbox=sandbox,
        harness=mock_harness,
        initial_prompt="Implement calc",
        verification_runner=runner,
    )

    assert passed
    assert healing_attempts == 1
    assert len(executions) == 2
    assert mock_harness.execute_task.call_count == 2
    # Verify second prompt contains error trace
    second_prompt = mock_harness.execute_task.call_args_list[1][1]["task_prompt"]
    assert "REPAIR ATTEMPT #1" in second_prompt
    assert "AssertionError" in second_prompt


def test_self_healing_exhausts_budget():
    sandbox = FakeSandbox()
    # All attempts fail
    sandbox.exec_results = [
        StepExecution("test", 1, "", "Fatal error", 0.5),
        StepExecution("test", 1, "", "Fatal error", 0.5),
    ]

    mock_harness = MagicMock(spec=AgentHarness)
    mock_harness.execute_task.return_value = HarnessResult(
        success=True,
        modified_files=["calc.py"],
    )

    runner = VerificationRunner([VerificationStep("test", ["pytest"])])
    healer = SelfHealingLoop(max_retries=1)

    passed, healing_attempts, executions, telemetry = healer.run_loop(
        sandbox=sandbox,
        harness=mock_harness,
        initial_prompt="Implement calc",
        verification_runner=runner,
    )

    assert not passed
    assert healing_attempts == 1
    assert len(executions) == 2
