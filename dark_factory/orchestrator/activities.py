"""Stateless workflow activities for Sovereign Dark Factory (Option C Architecture).

These functions encapsulate the core steps of a factory run and can be executed
either directly by the embedded SQLite engine or registered as Temporal Activities.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from dark_factory.domain.errors import DarkFactoryError
from dark_factory.domain.types import (
    EvidenceManifest,
    ModelTelemetry,
    RunStatus,
    StepExecution,
    TaskSpec,
)
from dark_factory.harness.base import AgentHarness
from dark_factory.sandbox.base import Sandbox
from dark_factory.sandbox.worktree import GitWorktreeSandbox
from dark_factory.storage.evidence import EvidenceLocker
from dark_factory.verification.healing import SelfHealingLoop
from dark_factory.verification.runner import VerificationRunner


def activity_create_sandbox(
    spec: TaskSpec,
    run_id: str,
    base_dir: str | Path | None = None,
) -> GitWorktreeSandbox:
    """Create and isolate a git worktree sandbox at the specified revision."""
    sandbox = GitWorktreeSandbox(
        repo_path=spec.repo_path,
        sandbox_id=run_id,
        base_dir=base_dir,
    )
    sandbox.create(base_rev=spec.base_rev)
    return sandbox


def activity_execute_task_and_verify(
    sandbox: Sandbox,
    harness: AgentHarness,
    spec: TaskSpec,
    status_callback: Callable[[RunStatus], None] | None = None,
) -> tuple[bool, int, list[StepExecution], ModelTelemetry | None]:
    """Execute code generation and deterministic verification with self-healing."""
    runner = VerificationRunner(spec.verification_steps, allow_no_verify=spec.allow_no_verify)
    healer = SelfHealingLoop(max_retries=spec.max_healing_attempts)

    passed, healing_attempts, executions, telemetry = healer.run_loop(
        sandbox=sandbox,
        harness=harness,
        initial_prompt=spec.task_prompt,
        verification_runner=runner,
        status_callback=status_callback,
    )
    return passed, healing_attempts, executions, telemetry


def activity_preserve_evidence(
    sandbox: Sandbox,
    locker: EvidenceLocker,
    manifest: EvidenceManifest,
    executions: list[StepExecution],
    healing_attempts: int,
    telemetry: ModelTelemetry | None,
) -> str:
    """Extract patch, assemble audit transcript, and preserve in evidence locker."""
    diff = sandbox.get_diff()

    # Build transcript
    transcript_lines = [f"=== RUN {manifest.run_id} TRANSCRIPT ==="]
    for ex in executions:
        status_str = "PASSED" if ex.passed else f"FAILED (exit {ex.exit_code})"
        transcript_lines.append(f"[{ex.step_id}] {status_str} ({ex.duration_sec:.2f}s)")
        if ex.stdout.strip():
            transcript_lines.append(f"STDOUT:\n{ex.stdout.strip()}")
        if ex.stderr.strip():
            transcript_lines.append(f"STDERR:\n{ex.stderr.strip()}")

    manifest.verification_results = executions
    manifest.healing_attempts = healing_attempts
    manifest.model_telemetry = telemetry
    manifest.completed_at = datetime.now(UTC).isoformat()

    locker.save_run(
        manifest=manifest,
        patch_content=diff,
        transcript="\n".join(transcript_lines),
    )
    return diff


def activity_apply_patch(
    repo_path: str | Path,
    patch_content: str,
    target_branch: str | None = None,
    commit_msg: str | None = None,
) -> str:
    """Apply a verified patch to the repository and optionally commit it to a branch."""
    repo = Path(repo_path).resolve()
    if not patch_content.strip():
        raise DarkFactoryError("Cannot apply empty patch.")

    # If target_branch requested, checkout new branch
    if target_branch:
        subprocess.run(
            ["git", "checkout", "-b", target_branch],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )

    # Apply patch via git apply
    apply_proc = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", "--exclude=*.pyc", "--exclude=__pycache__/*", "-"],
        cwd=repo,
        input=patch_content,
        text=True,
        capture_output=True,
    )
    if apply_proc.returncode != 0:
        raise DarkFactoryError(f"Failed to apply patch: {apply_proc.stderr}")

    # Commit if commit_msg provided
    if commit_msg:
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "--no-gpg-sign", "-m", commit_msg],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        rev_proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        return rev_proc.stdout.strip()

    return "applied"


def activity_cleanup_sandbox(sandbox: Sandbox) -> None:
    """Safely destroy sandbox."""
    try:
        sandbox.destroy()
    except Exception:
        pass
