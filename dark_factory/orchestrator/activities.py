"""Stateless workflow activities for Sovereign Dark Factory (Option C Architecture).

These functions encapsulate the core steps of a factory run and can be executed
directly by the embedded SQLite engine. Option C is a forward-looking seam; no Temporal worker
is registered in this release.
"""

from __future__ import annotations

import copy
import re
import subprocess
import sys
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from dark_factory.domain.errors import DarkFactoryError, RunTimeoutError
from dark_factory.domain.types import (
    AdversarialReport,
    EvidenceManifest,
    ExecutionPlan,
    ModelTelemetry,
    RunStatus,
    StepExecution,
    TaskSpec,
    VerificationStep,
)
from dark_factory.harness.base import AgentHarness
from dark_factory.sandbox.base import Sandbox
from dark_factory.sandbox.worktree import GitWorktreeSandbox
from dark_factory.storage.evidence import EvidenceLocker
from dark_factory.verification.adversarial import AdversarialAuditor
from dark_factory.verification.adversarial_mutator import AdversarialMutator
from dark_factory.verification.healing import SelfHealingLoop
from dark_factory.verification.runner import VerificationOutcome, VerificationRunner


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


@contextmanager
def _clamped_harness(owner: object, deadline: float | None):
    """Point `owner.harness` at a per-run copy whose per-call timeout is capped to the remaining deadline.

    The shared harness is never mutated, so concurrent runs cannot corrupt each other's timeout.
    Raises RunTimeoutError if the deadline has already passed.
    """
    if deadline is None:
        yield
        return
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RunTimeoutError("Run deadline exceeded before an LLM call could start.")
    original = owner.harness  # type: ignore[attr-defined]
    clamped = copy.copy(original)
    current = getattr(original, "timeout", None)
    if isinstance(current, (int, float)):
        clamped.timeout = max(1, min(current, int(remaining)))
    owner.harness = clamped  # type: ignore[attr-defined]
    try:
        yield
    finally:
        owner.harness = original  # type: ignore[attr-defined]


def activity_plan_task(
    run_id: str,
    spec: TaskSpec,
    sandbox: Sandbox,
    manifest: EvidenceManifest,
    harness: AgentHarness | None = None,
    deadline: float | None = None,
) -> ExecutionPlan | None:
    """Execute the reasoning planner to produce an ExecutionPlan before code generation."""
    if spec.skip_plan:
        return None
    if deadline is not None and time.monotonic() >= deadline:
        raise RunTimeoutError("Run deadline exceeded before task planning.")

    from dark_factory.harness.local_coder import LocalCoderHarness
    from dark_factory.planning.planner import LocalPlanner

    planner_model = spec.planner_model or spec.model
    if isinstance(harness, LocalCoderHarness) and harness.model == planner_model:
        planner_harness = harness
    elif isinstance(harness, LocalCoderHarness):
        planner_harness = LocalCoderHarness(model=planner_model)
    elif harness is not None and not hasattr(harness, "_call_model"):
        plan = ExecutionPlan(
            plan_id=f"plan-{run_id}",
            summary="Deterministic execution plan",
            invariants=[],
            steps=[],
            target_files=[],
        )
        manifest.execution_plan = plan
        return plan
    else:
        planner_harness = LocalCoderHarness(model=planner_model)

    planner = LocalPlanner(harness=planner_harness)

    # Lightweight repository context
    context = ""
    try:
        res = sandbox.execute(["git", "ls-files"])
        if res.passed and res.stdout.strip():
            context = f"Files in repository:\n{res.stdout.strip()[:1000]}"
    except Exception:
        pass

    with _clamped_harness(planner, deadline):
        plan = planner.generate_plan(
            task_prompt=spec.task_prompt,
            context=context,
            plan_id=f"plan-{run_id}",
        )
    manifest.execution_plan = plan
    return plan


def activity_execute_task_and_verify(
    sandbox: Sandbox,
    harness: AgentHarness,
    spec: TaskSpec,
    status_callback: Callable[[RunStatus], None] | None = None,
    deadline: float | None = None,
    plan: ExecutionPlan | None = None,
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

    initial_prompt = spec.task_prompt
    if plan and plan.summary:
        invariants_block = "\n".join(f"- {inv}" for inv in plan.invariants) if plan.invariants else "None specified"
        steps_block = "\n".join(f"- {step}" for step in plan.steps) if plan.steps else "None specified"
        initial_prompt = (
            f"{spec.task_prompt}\n\n"
            f"=== ARCHITECTURAL EXECUTION PLAN ===\n"
            f"Summary: {plan.summary}\n"
            f"Invariants:\n{invariants_block}\n"
            f"Implementation Steps:\n{steps_block}\n"
            f"Follow this plan strictly and make the minimal necessary changes."
        )

    passed, healing_attempts, executions, telemetry, repeated_failure_streak = healer.run_loop(
        sandbox=sandbox,
        harness=harness,
        initial_prompt=initial_prompt,
        verification_runner=runner,
        target_files=spec.target_files or None,
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


def activity_adversarial_audit(
    spec: TaskSpec,
    diff: str,
    manifest: EvidenceManifest,
    harness: AgentHarness | None = None,
    auditor: AdversarialAuditor | None = None,
    gate_summary: str = "",
    deadline: float | None = None,
) -> AdversarialReport | None:
    """Execute adversarial red-team audit on the generated diff before human review."""
    if spec.skip_adversarial:
        return None

    if auditor is None:
        from dark_factory.harness.local_coder import LocalCoderHarness

        if harness is not None and not isinstance(harness, LocalCoderHarness) and not hasattr(harness, "_call_model"):
            report = AdversarialReport(passed=True, summary="Deterministic audit passed.", findings=[])
            manifest.adversarial_report = report
            return report
        auditor = AdversarialAuditor(harness=harness)  # type: ignore[arg-type]

    with _clamped_harness(auditor, deadline):
        report = auditor.audit_patch(
            task_prompt=spec.task_prompt,
            patch=diff,
            gate_summary=gate_summary,
        )
    manifest.adversarial_report = report
    return report


def activity_adversarial_mutation(
    sandbox: Sandbox,
    harness: AgentHarness,
    spec: TaskSpec,
    manifest: EvidenceManifest,
    diff: str,
    status_callback: Callable[[RunStatus], None] | None = None,
    deadline: float | None = None,
    mutator: AdversarialMutator | None = None,
    healer: SelfHealingLoop | None = None,
    healing_attempts_so_far: int = 0,
) -> tuple[bool, int, list[StepExecution], ModelTelemetry | None]:
    """Synthesize active hostile unit tests to probe the patch and heal if probe fails."""
    if not spec.mutate_adversarial or not diff.strip():
        return True, 0, [], None

    from dark_factory.harness.local_coder import LocalCoderHarness
    from dark_factory.verification.adversarial_mutator import AdversarialMutator

    if mutator is None:
        mut_harness = harness if isinstance(harness, LocalCoderHarness) else LocalCoderHarness(model=spec.model)
        mutator = AdversarialMutator(harness=mut_harness)

    # Lightweight context
    context = ""
    try:
        res = sandbox.execute(["git", "ls-files"])
        if res.passed and res.stdout.strip():
            context = f"Files in repository:\n{res.stdout.strip()[:1000]}"
    except Exception:
        pass

    with _clamped_harness(mutator, deadline):
        probe_code = mutator.generate_probe(task_prompt=spec.task_prompt, patch=diff, context=context)
    if not probe_code:
        # Graceful fallback: syntax error or generation failure in probe
        return True, 0, [], None

    manifest.adversarial_test_code = probe_code
    probe_path = "test_adversarial_probe.py"
    sandbox.write_file(probe_path, probe_code.encode("utf-8"))

    # Probe step
    probe_step = VerificationStep(
        id="adversarial_probe",
        argv=[sys.executable, "-m", "pytest", probe_path],
        timeout_sec=60,
    )
    combined_steps = list(spec.verification_steps) + [probe_step]

    class AdversarialVerificationRunner(VerificationRunner):
        def run(self, sbox: Sandbox, deadline: float | None = None) -> VerificationOutcome:
            sbox.write_file(probe_path, probe_code.encode("utf-8"))
            return super().run(sbox, deadline=deadline)

    runner = AdversarialVerificationRunner(
        steps=combined_steps,
        allow_no_verify=spec.allow_no_verify,
        protected_paths=spec.protected_paths,
        allow_gate_edits=spec.allow_gate_edits,
        base_rev=spec.base_rev,
    )

    def cleanup_probe():
        try:
            sandbox.restore_paths([probe_path])
        except Exception:
            pass
        if hasattr(sandbox, "path"):
            try:
                (Path(sandbox.path) / probe_path).unlink(missing_ok=True)
            except Exception:
                pass

    def reverify_baseline() -> tuple[bool, list[StepExecution]]:
        """Re-run only the baseline gates on the final tree: the probe is LLM-authored code and must not
        be able to change the sources after they were verified."""
        base_runner = VerificationRunner(
            steps=list(spec.verification_steps),
            allow_no_verify=spec.allow_no_verify,
            protected_paths=spec.protected_paths,
            allow_gate_edits=spec.allow_gate_edits,
            base_rev=spec.base_rev,
        )
        base_outcome = base_runner.run(sandbox, deadline=deadline)
        return base_outcome.passed, [replace(ex, step_id=f"{ex.step_id}:reverify") for ex in base_outcome.executions]

    try:
        outcome = runner.run(sandbox, deadline=deadline)
        executions = list(outcome.executions)
        attempts_used = 0
        telemetry: ModelTelemetry | None = None
        passed = outcome.passed

        if not passed:
            # Probe failed!
            remaining_retries = spec.max_healing_attempts - healing_attempts_so_far
            if remaining_retries <= 0:
                return False, 0, executions, None

            if healer is None:
                healer = SelfHealingLoop(max_retries=remaining_retries)

            repair_prompt = (
                f"ORIGINAL TASK:\n{spec.task_prompt}\n\n"
                "Your previous implementation passed baseline verification, but an adversarial red-team stress test "
                f"found defects:\n\n{outcome.error_summary}\n\n"
                "Fix the application code to satisfy the requirements and pass all tests (baseline and adversarial).\n"
                "Provide complete file contents formatted in ```file:<path> ... ``` blocks."
            )

            passed, attempts, healed_executions, telemetry, _streak = healer.run_loop(
                sandbox=sandbox,
                harness=harness,
                initial_prompt=repair_prompt,
                verification_runner=runner,
                target_files=spec.target_files or None,
                status_callback=status_callback,
                deadline=deadline,
            )
            executions += healed_executions
            attempts_used = attempts + 1

        if passed:
            cleanup_probe()
            baseline_ok, baseline_execs = reverify_baseline()
            executions += baseline_execs
            passed = baseline_ok
        return passed, attempts_used, executions, telemetry
    finally:
        cleanup_probe()
