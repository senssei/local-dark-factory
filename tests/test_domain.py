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
