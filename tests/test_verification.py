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

    def restore_paths(self, paths: list[str], rev: str | None = None) -> list[str]:
        return []

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

    passed, healing_attempts, executions, telemetry, repeated_failure_streak = healer.run_loop(
        sandbox=sandbox,
        harness=mock_harness,
        initial_prompt="Implement calc",
        verification_runner=runner,
    )

    assert passed
    assert healing_attempts == 1
    assert len(executions) == 2
    assert repeated_failure_streak == 0
    assert mock_harness.execute_task.call_count == 2
    # Verify second prompt contains error trace
    second_prompt = mock_harness.execute_task.call_args_list[1][1]["task_prompt"]
    assert "REPAIR ATTEMPT #1" in second_prompt
    assert "AssertionError" in second_prompt


def test_self_healing_exhausts_budget():
    sandbox = FakeSandbox()
    # All attempts fail identically (the model re-derives the same broken fix every time)
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

    passed, healing_attempts, executions, telemetry, repeated_failure_streak = healer.run_loop(
        sandbox=sandbox,
        harness=mock_harness,
        initial_prompt="Implement calc",
        verification_runner=runner,
    )

    assert not passed
    assert healing_attempts == 1
    assert len(executions) == 2
    # Identical failure both times: detected as a repeated (stuck) failure.
    assert repeated_failure_streak == 1


def test_self_healing_treats_differing_only_in_duration_as_the_same_failure():
    """Real regression: two pytest runs with the identical outcome still differ in stdout because pytest
    appends a wall-clock summary line ("1 failed in 0.03s") that varies run to run. Without normalizing
    that out, the stuck-detector would flap between "stuck" and "not stuck" purely from timing noise."""
    sandbox = FakeSandbox()
    sandbox.exec_results = [
        StepExecution("test", 1, "1 failed, 2 passed in 0.02s", "", 0.02),
        StepExecution("test", 1, "1 failed, 2 passed in 0.05s", "", 0.05),
    ]

    mock_harness = MagicMock(spec=AgentHarness)
    mock_harness.execute_task.return_value = HarnessResult(success=True, modified_files=["calc.py"])

    runner = VerificationRunner([VerificationStep("test", ["pytest"])])
    healer = SelfHealingLoop(max_retries=1)

    passed, healing_attempts, executions, telemetry, repeated_failure_streak = healer.run_loop(
        sandbox=sandbox,
        harness=mock_harness,
        initial_prompt="Implement calc",
        verification_runner=runner,
    )

    assert not passed
    # Same real outcome, only the embedded duration differs: must still count as a repeat.
    assert repeated_failure_streak == 1


def test_self_healing_stuck_notice_appears_only_after_a_repeat():
    """The model re-derives the exact same wrong fix on every attempt: verify the repair prompt only
    carries the STUCK NOTICE starting from the *second* identical failure, not the first (a single failure
    isn't a "stuck" pattern yet — it takes a repeat to know the previous fix didn't change anything)."""
    sandbox = FakeSandbox()
    identical_failure = StepExecution("test", 1, "", "Fatal error", 0.5)
    sandbox.exec_results = [identical_failure, identical_failure, identical_failure]

    mock_harness = MagicMock(spec=AgentHarness)
    mock_harness.execute_task.return_value = HarnessResult(success=True, modified_files=["calc.py"])

    runner = VerificationRunner([VerificationStep("test", ["pytest"])])
    # max_retries=2 caps total harness calls at 3 (initial + 2 repairs), matching the 3 exec_results above.
    healer = SelfHealingLoop(max_retries=2)

    passed, healing_attempts, executions, telemetry, repeated_failure_streak = healer.run_loop(
        sandbox=sandbox,
        harness=mock_harness,
        initial_prompt="Implement calc",
        verification_runner=runner,
    )

    assert not passed
    assert len(executions) == 3
    # Two repeats of the same failure after the first occurrence.
    assert repeated_failure_streak == 2

    prompts = [call.kwargs["task_prompt"] for call in mock_harness.execute_task.call_args_list]
    assert "STUCK NOTICE" not in prompts[0]  # initial prompt, no failure yet
    assert "STUCK NOTICE" not in prompts[1]  # repair after the 1st failure: nothing to compare against yet
    assert "STUCK NOTICE" in prompts[2]  # repair after the 2nd (identical) failure: now flagged


def test_self_healing_no_stuck_notice_when_failures_differ():
    """A model trying different (still wrong) approaches each time must not be told it's stuck."""
    sandbox = FakeSandbox()
    sandbox.exec_results = [
        StepExecution("test", 1, "", "AssertionError: expected 1, got 2", 0.5),
        StepExecution("test", 1, "", "AssertionError: expected 1, got 3", 0.5),
        StepExecution("test", 1, "", "AssertionError: expected 1, got 4", 0.5),
    ]

    mock_harness = MagicMock(spec=AgentHarness)
    mock_harness.execute_task.return_value = HarnessResult(success=True, modified_files=["calc.py"])

    runner = VerificationRunner([VerificationStep("test", ["pytest"])])
    healer = SelfHealingLoop(max_retries=2)

    passed, healing_attempts, executions, telemetry, repeated_failure_streak = healer.run_loop(
        sandbox=sandbox,
        harness=mock_harness,
        initial_prompt="Implement calc",
        verification_runner=runner,
    )

    assert not passed
    assert repeated_failure_streak == 0
    for call in mock_harness.execute_task.call_args_list:
        assert "STUCK NOTICE" not in call.kwargs["task_prompt"]


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

    passed, attempts, executions, telemetry, repeated_failure_streak = healer.run_loop(
        sandbox=sandbox,
        harness=mock_harness,
        initial_prompt="Implement foo and bar in app.py",
        verification_runner=runner,
        status_callback=lambda st: status_events.append(st),
    )

    assert passed
    assert attempts == 1
    assert len(executions) == 2
    assert repeated_failure_streak == 0

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

    passed, attempts, executions, _, _ = healer.run_loop(
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


def test_verification_runner_restores_gates_before_run():
    sandbox = FakeSandbox()
    sandbox.exec_results = [
        StepExecution("test", 0, "Pass", "", 0.5),
    ]
    sandbox.restore_paths = MagicMock(return_value=["test_calc.py"])

    runner = VerificationRunner(
        steps=[VerificationStep("test", ["pytest", "test_calc.py"])],
        allow_gate_edits=False,
    )
    outcome = runner.run(sandbox)

    assert outcome.passed
    assert outcome.tampered_paths == ["test_calc.py"]
    assert sandbox.restore_paths.called

    # When allow_gate_edits is True, restore_paths should NOT be called
    sandbox2 = FakeSandbox()
    sandbox2.exec_results = [
        StepExecution("test", 0, "Pass", "", 0.5),
    ]
    sandbox2.restore_paths = MagicMock()

    runner_allowed = VerificationRunner(
        steps=[VerificationStep("test", ["pytest", "test_calc.py"])],
        allow_gate_edits=True,
    )
    outcome2 = runner_allowed.run(sandbox2)
    assert outcome2.passed
    assert not sandbox2.restore_paths.called


def test_default_gate_paths_keep_leading_dots():
    """`.github/...` must not be mangled into `github/...` (lstrip strips characters, not a prefix)."""
    runner = VerificationRunner(
        steps=[VerificationStep("lint", ["./.github/check.sh", ".venv/bin/pytest"])],
    )
    paths = runner.detect_default_gate_paths()
    assert ".github/check.sh" in paths
    assert ".venv/bin/pytest" in paths
    assert "github/check.sh" not in paths
    assert "venv/bin/pytest" not in paths


def test_default_gate_paths_protect_test_runner_config():
    runner = VerificationRunner(steps=[VerificationStep("t", ["pytest"])])
    paths = set(runner.detect_default_gate_paths())
    for expected in ("pyproject.toml", "setup.cfg", ".coveragerc", "pytest.ini", "tox.ini", "tests"):
        assert expected in paths
    # Config injected at any depth must be covered too.
    for name in ("conftest.py", "sitecustomize.py", "usercustomize.py"):
        assert f":(glob)**/{name}" in paths


def test_default_gate_paths_does_not_protect_lint_target():
    """A lint gate's argv names the file the agent must be free to edit, not a gate/test file: protecting
    it would silently revert the agent's fix to it before every verification pass."""
    runner = VerificationRunner(
        steps=[
            VerificationStep("pytest", ["python", "-m", "pytest", "test_calc.py"]),
            VerificationStep("ruff", ["python", "-m", "ruff", "check", "calc.py"]),
        ],
    )
    paths = set(runner.detect_default_gate_paths())
    assert "test_calc.py" in paths  # the actual test file is still protected
    assert "calc.py" not in paths  # the lint target is not
    assert "check" not in paths
    assert "ruff" not in paths


def test_default_gate_paths_lint_step_alone_still_protects_baseline():
    """Even a lint-only configuration keeps the fixed baseline (tests/, pyproject.toml, ...)."""
    runner = VerificationRunner(steps=[VerificationStep("mypy", ["mypy", "src/mymodule.py"])])
    paths = set(runner.detect_default_gate_paths())
    assert "src/mymodule.py" not in paths
    assert "pyproject.toml" in paths
    assert "tests" in paths


def test_runner_clamps_gate_timeout_to_remaining_deadline():
    import time

    seen = {}

    class RecordingSandbox(FakeSandbox):
        def execute(self, argv, cwd=None, env=None, timeout=300, step_id="exec"):
            seen["timeout"] = timeout
            return StepExecution(step_id, 0, "", "", 0.1)

    runner = VerificationRunner(steps=[VerificationStep("slow", ["./t.sh"], timeout_sec=300)])
    runner.run(RecordingSandbox(), deadline=time.monotonic() + 5)
    assert 1 <= seen["timeout"] <= 5


def test_self_healing_raises_run_timeout_with_partial_results():
    import time

    import pytest

    from dark_factory.domain.errors import RunTimeoutError

    harness = MagicMock(spec=AgentHarness)
    runner = VerificationRunner(steps=[VerificationStep("t", ["./t.sh"])])

    with pytest.raises(RunTimeoutError) as excinfo:
        SelfHealingLoop(max_retries=3).run_loop(
            sandbox=FakeSandbox(),
            harness=harness,
            initial_prompt="task",
            verification_runner=runner,
            deadline=time.monotonic() - 1,
        )
    assert excinfo.value.executions == []
    assert excinfo.value.healing_attempts == 0
    assert not harness.execute_task.called


def test_verification_runner_short_circuits_when_deadline_already_passed():
    """Spec §202: `clamps each gate's timeout to the time remaining`.

    A past deadline must short-circuit BEFORE invoking the next gate; otherwise the
    `max(1, int(remaining))` floor masks the timeout and the run overruns by one
    full second per gate.
    """
    import time

    import pytest

    from dark_factory.domain.errors import RunTimeoutError

    sandbox = FakeSandbox()
    sandbox.exec_results = [
        StepExecution("g1", 0, "ok", "", 0.1),
        StepExecution("g2", 0, "should not run", "", 0.1),
    ]
    sandbox.execute = MagicMock(side_effect=AssertionError("verification gate must not run past deadline"))
    runner = VerificationRunner(
        steps=[
            VerificationStep("g1", ["./g1.sh"]),
            VerificationStep("g2", ["./g2.sh"]),
        ],
    )

    with pytest.raises(RunTimeoutError):
        runner.run(sandbox, deadline=time.monotonic() - 1.0)

    assert not sandbox.execute.called


def test_self_healing_keeps_the_context_window_in_aggregated_telemetry():
    sandbox = FakeSandbox()
    sandbox.exec_results = [
        StepExecution("test", 1, "", "boom", 0.5),
        StepExecution("test", 0, "Pass", "", 0.5),
    ]
    mock_harness = MagicMock(spec=AgentHarness)
    mock_harness.execute_task.side_effect = [
        HarnessResult(
            success=True,
            modified_files=["a.py"],
            telemetry=ModelTelemetry(engine="ollama", model_name="m", prompt_tokens=1, num_ctx=4096),
        ),
        HarnessResult(
            success=True,
            modified_files=["a.py"],
            telemetry=ModelTelemetry(engine="ollama", model_name="m", prompt_tokens=1, num_ctx=8192),
        ),
    ]
    runner = VerificationRunner([VerificationStep("test", ["pytest"])])
    _, _, _, telemetry, _ = SelfHealingLoop(max_retries=2).run_loop(
        sandbox=sandbox, harness=mock_harness, initial_prompt="x", verification_runner=runner
    )
    assert telemetry is not None and telemetry.num_ctx == 8192


def test_self_healing_records_the_harness_error_when_it_gives_up():
    mock_harness = MagicMock(spec=AgentHarness)
    mock_harness.execute_task.return_value = HarnessResult(success=False, error="Prompt needs about 20000 tokens")
    runner = VerificationRunner([VerificationStep("test", ["pytest"])])
    passed, attempts, executions, _, _ = SelfHealingLoop(max_retries=1).run_loop(
        sandbox=FakeSandbox(), harness=mock_harness, initial_prompt="x", verification_runner=runner
    )
    assert not passed
    assert [ex.step_id for ex in executions] == ["harness"]
    assert "Prompt needs about 20000 tokens" in executions[0].stderr
    assert not executions[0].passed


def test_self_healing_caps_a_huge_failure_trace_in_the_repair_prompt():
    sandbox = FakeSandbox()
    huge = "E  noise\n" * 12000 + "FINAL SUMMARY LINE"
    sandbox.exec_results = [StepExecution("test", 1, "", huge, 0.5), StepExecution("test", 0, "ok", "", 0.5)]
    mock_harness = MagicMock(spec=AgentHarness)
    mock_harness.execute_task.return_value = HarnessResult(success=True, modified_files=["a.py"])
    runner = VerificationRunner([VerificationStep("test", ["pytest"])])
    SelfHealingLoop(max_retries=2).run_loop(
        sandbox=sandbox, harness=mock_harness, initial_prompt="task", verification_runner=runner
    )
    repair = mock_harness.execute_task.call_args_list[1][1]["task_prompt"]
    assert len(repair) < 12000
    assert "FINAL SUMMARY LINE" in repair  # the tail (pytest summary) is kept
    assert "truncated" in repair.lower()


def test_self_healing_resets_the_failure_streak_when_the_harness_fails_last():
    sandbox = FakeSandbox()
    same = StepExecution("test", 1, "", "same error", 0.1)
    sandbox.exec_results = [same, same, same]
    mock_harness = MagicMock(spec=AgentHarness)
    mock_harness.execute_task.side_effect = [
        HarnessResult(success=True, modified_files=["a.py"]),
        HarnessResult(success=True, modified_files=["a.py"]),
        HarnessResult(success=False, error="Prompt needs too much"),
        HarnessResult(success=False, error="Prompt needs too much"),
    ]
    runner = VerificationRunner([VerificationStep("test", ["pytest"])])
    passed, _, executions, _, streak = SelfHealingLoop(max_retries=3).run_loop(
        sandbox=sandbox, harness=mock_harness, initial_prompt="x", verification_runner=runner
    )
    assert not passed
    assert executions[-1].step_id == "harness"
    assert streak == 0
