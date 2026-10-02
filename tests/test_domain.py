"""Unit tests for dark_factory.domain."""

from dark_factory.domain import (
    EvidenceManifest,
    RunStatus,
    StepExecution,
    TaskSpec,
)


def test_run_status_terminal_states():
    assert not RunStatus.PENDING.is_terminal
    assert not RunStatus.AGENT_RUNNING.is_terminal
    assert not RunStatus.VERIFYING.is_terminal
    assert not RunStatus.AWAITING_REVIEW.is_terminal

    assert RunStatus.APPROVED.is_terminal
    assert RunStatus.REJECTED.is_terminal
    assert RunStatus.FAILED.is_terminal
    assert RunStatus.TIMED_OUT.is_terminal
    assert RunStatus.CANCELLED.is_terminal


def test_step_execution_passed():
    step_ok = StepExecution(
        step_id="build",
        exit_code=0,
        stdout="Build succeeded",
        stderr="",
        duration_sec=1.2,
    )
    assert step_ok.passed

    step_failed = StepExecution(
        step_id="test",
        exit_code=1,
        stdout="",
        stderr="Tests failed",
        duration_sec=2.5,
    )
    assert not step_failed.passed

    step_timeout = StepExecution(
        step_id="slow",
        exit_code=0,
        stdout="",
        stderr="",
        duration_sec=300.0,
        timed_out=True,
    )
    assert not step_timeout.passed


def test_task_spec_defaults():
    task = TaskSpec(
        repo_path="/path/to/repo",
        task_prompt="Refactor database layer",
    )
    assert task.base_rev == "HEAD"
    assert task.agent == "local-coder"
    assert task.model == "qwen2.5-coder:14b"
    assert task.max_healing_attempts == 3
    assert len(task.verification_steps) == 0


def test_evidence_manifest_creation():
    manifest = EvidenceManifest.create(
        run_id="run-12345",
        repo_path="/path/to/repo",
        base_rev="abc1234",
    )
    assert manifest.run_id == "run-12345"
    assert manifest.status == RunStatus.PENDING
    assert manifest.patch_size_bytes == 0
    assert manifest.model_telemetry is None
    assert manifest.created_at is not None


def test_adversarial_report_contracts():
    from dark_factory.domain import AdversarialFinding, AdversarialReport

    finding = AdversarialFinding(
        severity="WARN",
        category="boundary",
        summary="Missing null check",
        details="Function does not handle None input on arg 1",
    )
    assert finding.severity == "WARN"
    assert finding.category == "boundary"

    report = AdversarialReport(
        passed=False,
        summary="Audit failed with 1 warning",
        findings=[finding],
    )
    assert not report.passed
    assert len(report.findings) == 1

    manifest = EvidenceManifest.create(
        run_id="run-adv-01",
        repo_path="/tmp/repo",
        base_rev="abc1234",
    )
    assert manifest.adversarial_report is None


def test_execution_plan_contracts():
    from dark_factory.domain import ExecutionPlan

    plan = ExecutionPlan(
        plan_id="plan-test-01",
        summary="Refactor parser to support streaming",
        invariants=["No memory accumulation on large payloads", "Preserve error handling contract"],
        steps=["1. Replace json.loads with ijson stream", "2. Update unit tests"],
        target_files=["parser.py", "tests/test_parser.py"],
        raw_plan="Detailed plan text",
    )
    assert plan.plan_id == "plan-test-01"
    assert len(plan.invariants) == 2
    assert len(plan.steps) == 2
    assert plan.target_files == ["parser.py", "tests/test_parser.py"]

    task = TaskSpec(repo_path="/tmp/repo", task_prompt="Streaming parser")
    assert task.planner_model is None
    assert task.skip_plan is False

    manifest = EvidenceManifest.create(run_id="run-plan-01", repo_path="/tmp/repo", base_rev="abc1234")
    assert manifest.execution_plan is None


def test_adversarial_mutation_contracts():
    task = TaskSpec(repo_path="/tmp/repo", task_prompt="Fix boundary check")
    assert task.mutate_adversarial is False

    manifest = EvidenceManifest.create(run_id="run-mut-01", repo_path="/tmp/repo", base_rev="abc1234")
    assert manifest.adversarial_test_code is None
