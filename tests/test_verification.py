"""Unit tests for VerificationRunner and SelfHealingLoop."""

from unittest.mock import MagicMock

from dark_factory.domain.types import ModelTelemetry, RunStatus, StepExecution, VerificationStep
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


def test_verification_runner_zero_gates_fails():
    sandbox = FakeSandbox()
    runner = VerificationRunner(steps=[], allow_no_verify=False)
    outcome = runner.run(sandbox)

    assert not outcome.passed
    assert outcome.failed_step is not None
    assert "Zero verification gates configured" in outcome.failed_step.stderr


def test_verification_runner_zero_gates_allowed():
    sandbox = FakeSandbox()
    runner = VerificationRunner(steps=[], allow_no_verify=True)
    outcome = runner.run(sandbox)

    assert outcome.passed
    assert outcome.executions == []


def test_self_healing_retains_original_task_and_aggregates_telemetry():
    sandbox = FakeSandbox()
    # 1st attempt fails verification, 2nd passes
    sandbox.exec_results = [
        StepExecution("test", 1, "", "NameError: name 'foo' is not defined", 0.5),
        StepExecution("test", 0, "Pass", "", 0.5),
    ]

    mock_harness = MagicMock(spec=AgentHarness)
    mock_harness.execute_task.side_effect = [
        HarnessResult(
            success=True,
            modified_files=["app.py"],
            telemetry=ModelTelemetry(
                engine="ollama",
                model_name="qwen2.5-coder:14b",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                duration_sec=1.0,
                tokens_per_sec=50.0,
            ),
        ),
        HarnessResult(
            success=True,
            modified_files=["app.py"],
            telemetry=ModelTelemetry(
                engine="ollama",
                model_name="qwen2.5-coder:14b",
                prompt_tokens=200,
                completion_tokens=60,
                total_tokens=260,
                duration_sec=1.5,
                tokens_per_sec=40.0,
            ),
        ),
    ]

    status_events: list[RunStatus] = []
    runner = VerificationRunner([VerificationStep("test", ["pytest"])])
    healer = SelfHealingLoop(max_retries=2)

    passed, attempts, executions, telemetry = healer.run_loop(
        sandbox=sandbox,
        harness=mock_harness,
        initial_prompt="Implement foo and bar in app.py",
        verification_runner=runner,
        status_callback=lambda st: status_events.append(st),
    )

    assert passed
    assert attempts == 1
    assert len(executions) == 2

    # Check that initial prompt was retained in 2nd call
    call_args_2 = mock_harness.execute_task.call_args_list[1][1]["task_prompt"]
    assert "ORIGINAL TASK:\nImplement foo and bar in app.py" in call_args_2
    assert "REPAIR ATTEMPT #1 OF 2:" in call_args_2
    assert "NameError: name 'foo' is not defined" in call_args_2

    # Check telemetry aggregation
    assert telemetry is not None
    assert telemetry.prompt_tokens == 300
    assert telemetry.completion_tokens == 110
    assert telemetry.total_tokens == 410
    assert telemetry.duration_sec == 2.5

    # Check status transitions
    assert RunStatus.VERIFYING in status_events
    assert RunStatus.SELF_HEALING in status_events


def test_self_healing_handles_harness_syntax_failure_as_retry():
    sandbox = FakeSandbox()
    sandbox.exec_results = [
        StepExecution("test", 0, "Pass", "", 0.5),
    ]

    mock_harness = MagicMock(spec=AgentHarness)
    mock_harness.execute_task.side_effect = [
        HarnessResult(
            success=False,
            error="No valid file blocks found in model response.",
            telemetry=None,
        ),
        HarnessResult(
            success=True,
            modified_files=["fixed.py"],
            telemetry=None,
        ),
    ]

    runner = VerificationRunner([VerificationStep("test", ["pytest"])])
    healer = SelfHealingLoop(max_retries=2)

    passed, attempts, executions, _ = healer.run_loop(
        sandbox=sandbox,
        harness=mock_harness,
        initial_prompt="Create fixed.py",
        verification_runner=runner,
    )

    assert passed
    assert attempts == 1
    second_call_prompt = mock_harness.execute_task.call_args_list[1][1]["task_prompt"]
    assert "ORIGINAL TASK:\nCreate fixed.py" in second_call_prompt
    assert "Your previous response failed to apply: No valid file blocks found in model response." in second_call_prompt
