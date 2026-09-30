"""Stateless workflow activities for Sovereign Dark Factory (Option C Architecture).

These functions encapsulate the core steps of a factory run and can be executed
directly by the embedded SQLite engine. Option C is a forward-looking seam; no Temporal worker
is registered in this release.
"""

from __future__ import annotations

import re
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
    deadline: float | None = None,
) -> tuple[bool, int, list[StepExecution], ModelTelemetry | None, int]:
    """Execute code generation and deterministic verification with self-healing."""
    runner = VerificationRunner(
        steps=spec.verification_steps,
        allow_no_verify=spec.allow_no_verify,
        protected_paths=spec.protected_paths,
        allow_gate_edits=spec.allow_gate_edits,
        base_rev=spec.base_rev,
    )
    healer = SelfHealingLoop(max_retries=spec.max_healing_attempts)

    passed, healing_attempts, executions, telemetry, repeated_failure_streak = healer.run_loop(
        sandbox=sandbox,
        harness=harness,
        initial_prompt=spec.task_prompt,
        verification_runner=runner,
        status_callback=status_callback,
        deadline=deadline,
    )
    return passed, healing_attempts, executions, telemetry, repeated_failure_streak


def activity_preserve_evidence(
    sandbox: Sandbox,
    locker: EvidenceLocker,
    manifest: EvidenceManifest,
    executions: list[StepExecution],
    healing_attempts: int,
    telemetry: ModelTelemetry | None,
    diff: str | None = None,
) -> str:
    """Extract patch (unless already extracted), assemble audit transcript, and preserve in evidence locker."""
    if diff is None:
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


_C_ESCAPES = {"a": 7, "b": 8, "t": 9, "n": 10, "v": 11, "f": 12, "r": 13, '"': 34, "\\": 92}
_QUOTED_TOKEN_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')


def _c_unquote(text: str) -> str:
    """Decode git's C-style quoting (octal escapes for non-ASCII bytes, \\t, \\", ...)."""
    out = bytearray()
    i = 0
    while i < len(text):
        ch = text[i]
        if ch != "\\" or i + 1 >= len(text):
            out.extend(ch.encode("utf-8"))
            i += 1
            continue
        nxt = text[i + 1]
        if nxt in "01234567":
            digits = text[i + 1 : i + 4]
            octal = re.match(r"[0-7]{1,3}", digits)
            assert octal is not None
            out.append(int(octal.group(0), 8) & 0xFF)
            i += 1 + len(octal.group(0))
        else:
            out.append(_C_ESCAPES.get(nxt, ord(nxt)))
            i += 2
    return out.decode("utf-8", errors="replace")


def _header_path(rest: str) -> str | None:
    """Extract the file path from the tail of a `diff --git` header (patches are rename-free: a/X b/X)."""
    if rest.startswith('"'):
        tokens = _QUOTED_TOKEN_RE.findall(rest)
        return _c_unquote(tokens[-1]).removeprefix("b/") if tokens else None
    # Unquoted: "a/<X> b/<X>" so the two halves around the single separating space are identical.
    length = len(rest) - 5
    if length > 0 and length % 2 == 0:
        n = length // 2
        if rest.startswith("a/") and rest[2 + n : 5 + n] == " b/" and rest[2 : 2 + n] == rest[5 + n :]:
            return rest[5 + n :]
    parts = rest.split()
    return parts[-1].removeprefix("b/") if len(parts) == 2 else None


def parse_patch_files(patch_content: str) -> list[str]:
    """Extract list of target file paths from git unified diff (spaces and quoted paths supported)."""
    files = set()
    for line in patch_content.splitlines():
        if line.startswith("diff --git "):
            path = _header_path(line.removeprefix("diff --git "))
            if path:
                files.add(path)
    return sorted(files)


def _git(repo: Path, *args: str, check: bool = True, input_text: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "--literal-pathspecs", *args],
        cwd=repo,
        input=input_text,
        text=True,
        errors="replace",  # a non-ASCII path outside the host locale must not raise UnicodeDecodeError
        capture_output=True,
        check=check,
    )


def _git_error(action: str, exc: subprocess.CalledProcessError) -> DarkFactoryError:
    detail = (exc.stderr or exc.stdout or "").strip()
    return DarkFactoryError(f"{action} failed: {detail}")


def _rollback_apply(repo: Path, files: list[str], original_ref: str, new_branch: str | None) -> None:
    """Best-effort restore of the host repo after a failed apply/commit (target files were clean beforehand)."""
    if files:
        _git(repo, "reset", "-q", "HEAD", "--", *files, check=False)
        tracked = _git(repo, "ls-files", "--", *files, check=False).stdout.splitlines()
        if tracked:
            _git(repo, "checkout", "-q", "--", *tracked, check=False)
        _git(repo, "clean", "-fq", "--", *files, check=False)
    if new_branch:
        _git(repo, "checkout", "-q", original_ref, check=False)
        _git(repo, "branch", "-D", new_branch, check=False)


def activity_apply_patch(
    repo_path: str | Path,
    patch_content: str,
    target_branch: str | None = None,
    commit_msg: str | None = None,
) -> str:
    """Apply a verified patch to the repository and optionally commit it to a branch.

    Atomic with respect to the host repo: refuses to touch files with uncommitted changes, and if applying
    or committing fails after a branch was created, the original branch is restored and the new one deleted.
    """
    repo = Path(repo_path).resolve()
    if not patch_content.strip():
        raise DarkFactoryError("Cannot apply empty patch.")

    patch_files = parse_patch_files(patch_content)

    # 1. Never mix the operator's work-in-progress into the factory's commit
    if patch_files:
        dirty = _git(repo, "status", "--porcelain", "--", *patch_files, check=False).stdout.strip()
        if dirty:
            raise DarkFactoryError(f"Refusing to apply: target files have uncommitted changes:\n{dirty}")

    # 2. Pre-check patch applies cleanly before touching working tree or checking out branch
    check_proc = _git(
        repo,
        "apply",
        "--check",
        "--whitespace=nowarn",
        "--exclude=*.pyc",
        "--exclude=__pycache__/*",
        "-",
        check=False,
        input_text=patch_content,
    )
    if check_proc.returncode != 0:
        raise DarkFactoryError(f"Patch does not apply cleanly to target repository: {check_proc.stderr}")

    original_ref = _git(repo, "rev-parse", "--abbrev-ref", "HEAD", check=False).stdout.strip()
    if original_ref in ("", "HEAD"):  # detached HEAD
        original_ref = _git(repo, "rev-parse", "HEAD", check=False).stdout.strip()

    # If target_branch requested, checkout new branch
    if target_branch:
        try:
            _git(repo, "checkout", "-b", target_branch)
        except subprocess.CalledProcessError as e:
            raise _git_error(f"Creating branch '{target_branch}'", e) from e

    try:
        # 3. Apply patch via git apply
        apply_proc = _git(
            repo,
            "apply",
            "--whitespace=nowarn",
            "--exclude=*.pyc",
            "--exclude=__pycache__/*",
            "-",
            check=False,
            input_text=patch_content,
        )
        if apply_proc.returncode != 0:
            raise DarkFactoryError(f"Failed to apply patch: {apply_proc.stderr}")

        # 4. Stage ONLY modified files from patch (never indiscriminate git add .)
        if commit_msg:
            if patch_files:
                _git(repo, "add", "--", *patch_files)
            else:
                _git(repo, "add", "-u")

            _git(repo, "commit", "--no-gpg-sign", "-m", commit_msg)
            return _git(repo, "rev-parse", "HEAD").stdout.strip()
    except subprocess.CalledProcessError as e:
        _rollback_apply(repo, patch_files, original_ref, target_branch)
        raise _git_error("Committing patch", e) from e
    except DarkFactoryError:
        _rollback_apply(repo, patch_files, original_ref, target_branch)
        raise

    return "applied"


def activity_cleanup_sandbox(sandbox: Sandbox) -> None:
    """Safely destroy sandbox."""
    try:
        sandbox.destroy()
    except Exception:
        pass
