"""Unit tests for DurableEngine and state orchestration."""

import concurrent.futures
import subprocess
import sys
from pathlib import Path

import pytest

from dark_factory.domain.errors import DarkFactoryError, WorkflowStateError
from dark_factory.domain.types import (
    ModelTelemetry,
    RunStatus,
    TaskSpec,
    VerificationStep,
)
from dark_factory.harness.base import AgentHarness, HarnessResult
from dark_factory.orchestrator import DurableEngine
from dark_factory.orchestrator.activities import activity_apply_patch, parse_patch_files
from dark_factory.sandbox.base import Sandbox


@pytest.fixture
def mock_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Factory Operator"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "operator@factory.local"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True, capture_output=True)

    (repo / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    (repo / "test_calc.py").write_text("from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial baseline"], cwd=repo, check=True, capture_output=True)
    return repo


class MockRepairHarness(AgentHarness):
    """Harness that fixes the bug in calc.py."""

    def execute_task(self, sandbox: Sandbox, task_prompt: str, target_files=None):
        # Fix the bug
        sandbox.write_file("calc.py", b"def add(a, b):\n    return a + b\n")
        return HarnessResult(
            success=True,
            modified_files=["calc.py"],
            telemetry=ModelTelemetry(
                engine="ollama",
                model_name="qwen2.5-coder:14b",
                prompt_tokens=50,
                completion_tokens=50,
                total_tokens=100,
                tokens_per_sec=45.0,
            ),
        )


def test_durable_engine_e2e_approval_flow(mock_repo: Path, tmp_path: Path):
    storage = tmp_path / ".factory"
    engine = DurableEngine(storage_dir=storage)

    spec = TaskSpec(
        repo_path=str(mock_repo),
        task_prompt="Fix bug in add function in calc.py",
        verification_steps=[
            VerificationStep(id="pytest", argv=[sys.executable, "-m", "pytest", "test_calc.py"]),
        ],
    )

    harness = MockRepairHarness()
    statuses = []

    # Execute Run
    manifest = engine.execute_run(
        spec=spec,
        harness=harness,
        run_id="run-e2e-001",
        status_callback=lambda st: statuses.append(st),
    )

    assert manifest.run_id == "run-e2e-001"
    assert manifest.status == RunStatus.AWAITING_REVIEW
    assert manifest.patch_size_bytes > 0
    assert len(manifest.verification_results) == 1
    assert manifest.verification_results[0].passed
    assert RunStatus.CREATING_SANDBOX in statuses
    assert RunStatus.AGENT_RUNNING in statuses
    assert RunStatus.AWAITING_REVIEW in statuses

    # Operator Reviews and Approves
    approved_manifest = engine.review_run(
        run_id="run-e2e-001",
        approve=True,
        target_branch="feature/fixed-calc",
        note="Approved by AI Factory Manager",
    )

    assert approved_manifest.status == RunStatus.APPROVED
    assert approved_manifest.resulting_rev is not None

    # Verify that mock_repo is now on feature/fixed-calc and test passes!
    test_run = subprocess.run(
        [sys.executable, "-m", "pytest", "test_calc.py"], cwd=mock_repo, capture_output=True, text=True
    )
    assert test_run.returncode == 0


def test_durable_engine_rejection_flow(mock_repo: Path, tmp_path: Path):
    storage = tmp_path / ".factory"
    engine = DurableEngine(storage_dir=storage)

    spec = TaskSpec(
        repo_path=str(mock_repo),
        task_prompt="Fix bug",
        verification_steps=[
            VerificationStep(id="test", argv=[sys.executable, "-m", "pytest", "test_calc.py"]),
        ],
    )

    harness = MockRepairHarness()
    manifest = engine.execute_run(spec=spec, harness=harness, run_id="run-e2e-002")
    assert manifest.status == RunStatus.AWAITING_REVIEW

    # Operator Rejects
    rejected_manifest = engine.review_run(
        run_id="run-e2e-002",
        approve=False,
        note="Rejected: use typed return annotations",
    )
    assert rejected_manifest.status == RunStatus.REJECTED
    assert rejected_manifest.operator_notes == "Rejected: use typed return annotations"


def test_durable_engine_recovery(mock_repo: Path, tmp_path: Path):
    storage = tmp_path / ".factory"
    engine = DurableEngine(storage_dir=storage)

    # Insert an incomplete run directly into SQLite AND an awaiting_review run
    with engine._get_connection() as conn:
        conn.execute(
            """
            INSERT INTO runs (run_id, repo_path, base_rev, status, created_at, updated_at)
            VALUES ('run-crashed', ?, 'HEAD', 'AGENT_RUNNING', '2026-09-20T10:00:00Z', '2026-09-20T10:00:00Z');
            """,
            (str(mock_repo),),
        )
        conn.execute(
            """
            INSERT INTO runs (run_id, repo_path, base_rev, status, created_at, updated_at)
            VALUES ('run-awaiting', ?, 'HEAD', 'AWAITING_REVIEW', '2026-09-20T10:00:00Z', '2026-09-20T10:00:00Z');
            """,
            (str(mock_repo),),
        )

    # Create dummy dead sandbox folder for crashed run
    dead_sandbox = storage / "sandboxes" / "run-crashed"
    dead_sandbox.mkdir(parents=True)
    (dead_sandbox / "temp.txt").write_text("orphan")

    # Create another folder in sandboxes that should NOT be touched
    keep_sandbox = storage / "sandboxes" / "other-dir"
    keep_sandbox.mkdir(parents=True)
    (keep_sandbox / "keep.txt").write_text("stay")

    recovered = engine.recover()
    assert "run-crashed" in recovered
    assert "run-awaiting" not in recovered

    # Verify status changed to FAILED in DB for crashed run
    with engine._get_connection() as conn:
        row_crashed = conn.execute("SELECT status FROM runs WHERE run_id = 'run-crashed';").fetchone()
        assert row_crashed["status"] == "FAILED"

        # Verify AWAITING_REVIEW was preserved!
        row_awaiting = conn.execute("SELECT status FROM runs WHERE run_id = 'run-awaiting';").fetchone()
        assert row_awaiting["status"] == "AWAITING_REVIEW"

    # Verify dead sandbox removed, but other directory preserved
    assert not dead_sandbox.exists()
    assert keep_sandbox.exists()


def test_non_orphan_statuses_derived_from_run_status_enum():
    """recover()'s exclusion set must track RunStatus, not a hand-maintained string list."""
    from dark_factory.orchestrator.engine import _NON_ORPHAN_STATUSES

    expected = {s.value for s in RunStatus if s.is_terminal} | {RunStatus.AWAITING_REVIEW.value}
    assert _NON_ORPHAN_STATUSES == expected
    # SELF_HEALING/VERIFYING/etc. are in-flight and must remain orphan-eligible.
    assert RunStatus.SELF_HEALING.value not in _NON_ORPHAN_STATUSES
    assert RunStatus.VERIFYING.value not in _NON_ORPHAN_STATUSES


def test_git_helper_subprocess_calls_are_locale_safe(monkeypatch, mock_repo: Path):
    """A non-ASCII path outside the host locale must not surface as UnicodeDecodeError; every text-mode
    git subprocess call in the apply-patch path must pass errors='replace'."""
    from dark_factory.orchestrator import activities

    calls: list[dict] = []
    real_run = subprocess.run

    def spy(*args, **kwargs):
        calls.append(kwargs)
        return real_run(*args, **kwargs)

    monkeypatch.setattr(activities.subprocess, "run", spy)
    activities._git(mock_repo, "status", "--porcelain")

    assert calls
    assert all(c.get("errors") == "replace" for c in calls if c.get("text"))


def test_worktree_git_calls_are_locale_safe(monkeypatch, mock_repo: Path, tmp_path: Path):
    from dark_factory.sandbox import GitWorktreeSandbox
    from dark_factory.sandbox import worktree as worktree_module

    calls: list[dict] = []
    real_run = subprocess.run

    def spy(*args, **kwargs):
        calls.append(kwargs)
        return real_run(*args, **kwargs)

    monkeypatch.setattr(worktree_module.subprocess, "run", spy)
    sandbox = GitWorktreeSandbox(repo_path=mock_repo, sandbox_id="locale-check", base_dir=tmp_path / "sb")
    sandbox.create()
    try:
        sandbox.write_file("f.txt", b"x")
        sandbox.get_diff()
        sandbox.restore_paths(["f.txt"])
    finally:
        sandbox.destroy()

    assert calls
    assert all(c.get("errors") == "replace" for c in calls if c.get("text"))


def test_sandbox_restore_paths_contract_documents_glob_pathspecs():
    """Doc-level guard for the 10.6 restore_paths finding: the abstract contract must call out that
    implementations have to honor `:(glob)` pathspec magic, not just literal filesystem paths, so a
    future Sandbox (e.g. DockerSandbox) can't silently break gate protection for nested files."""
    from dark_factory.sandbox.base import Sandbox

    assert ":(glob)" in Sandbox.restore_paths.__doc__


def test_activity_parse_patch_files():
    sample_diff = """diff --git a/calc.py b/calc.py
--- a/calc.py
+++ b/calc.py
@@ -1,2 +1,2 @@
-def add(a, b): return a - b
+def add(a, b): return a + b
diff --git a/src/utils/helper.py b/src/utils/helper.py
--- /dev/null
+++ b/src/utils/helper.py
@@ -0,0 +1 @@
+x = 1
"""
    files = parse_patch_files(sample_diff)
    assert files == ["calc.py", "src/utils/helper.py"]


def test_activity_apply_patch_corrupt_patch_fails_cleanly(mock_repo: Path):
    corrupt_patch = """diff --git a/calc.py b/calc.py
--- a/calc.py
+++ b/calc.py
@@ -99,2 +99,2 @@
-nonexistent line
+replacement
"""
    with pytest.raises(DarkFactoryError, match="Patch does not apply cleanly"):
        activity_apply_patch(
            repo_path=mock_repo,
            patch_content=corrupt_patch,
            target_branch="branch-corrupt",
            commit_msg="attempt corrupt patch",
        )

    # Verify repository working directory was left clean!
    status_res = subprocess.run(["git", "status", "--porcelain"], cwd=mock_repo, capture_output=True, text=True)
    assert status_res.stdout.strip() == ""


def test_review_run_sha256_mismatch(mock_repo: Path, tmp_path: Path):
    storage = tmp_path / ".factory"
    engine = DurableEngine(storage_dir=storage)

    spec = TaskSpec(
        repo_path=str(mock_repo),
        task_prompt="Fix bug",
        verification_steps=[
            VerificationStep(id="pytest", argv=[sys.executable, "-m", "pytest", "test_calc.py"]),
        ],
    )

    manifest = engine.execute_run(spec=spec, harness=MockRepairHarness(), run_id="run-tampered")
    assert manifest.status == RunStatus.AWAITING_REVIEW
    assert manifest.patch_sha256 is not None

    # Tamper with diff.patch on disk
    patch_file = storage / "runs" / "run-tampered" / "diff.patch"
    patch_file.write_text(patch_file.read_text() + "\n# EVIL TAMPERING\n")

    # Attempt to approve tampered run
    with pytest.raises(WorkflowStateError, match="Patch integrity check failed"):
        engine.review_run(run_id="run-tampered", approve=True)


def _make_patch(repo: Path, tmp_path: Path, files: dict[str, bytes], sandbox_id: str = "patchgen") -> str:
    """Produce a real patch by writing `files` into a throw-away sandbox of `repo`."""
    from dark_factory.sandbox import GitWorktreeSandbox

    sandbox = GitWorktreeSandbox(repo_path=repo, sandbox_id=sandbox_id, base_dir=tmp_path / "patchgen")
    sandbox.create()
    try:
        for rel, content in files.items():
            sandbox.write_file(rel, content)
        return sandbox.get_diff()
    finally:
        sandbox.destroy()


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def test_parse_patch_files_handles_spaces_and_quoted_paths():
    diff = (
        "diff --git a/my file.py b/my file.py\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/my file.py\t\n"
        "@@ -0,0 +1 @@\n"
        "+x = 1\n"
        'diff --git "a/z\\305\\202a.py" "b/z\\305\\202a.py"\n'
        "new file mode 100644\n"
        "--- /dev/null\n"
        '+++ "b/z\\305\\202a.py"\n'
        "@@ -0,0 +1 @@\n"
        "+y = 2\n"
        "diff --git a/blob.bin b/blob.bin\n"
        "new file mode 100644\n"
        "GIT binary patch\n"
    )
    assert parse_patch_files(diff) == ["blob.bin", "my file.py", "zła.py"]


def test_apply_patch_commits_odd_filenames_and_deletions(mock_repo: Path, tmp_path: Path):
    (mock_repo / "old.txt").write_text("legacy\n")
    _git(mock_repo, "add", "old.txt")
    _git(mock_repo, "commit", "-m", "add old.txt")

    from dark_factory.sandbox import GitWorktreeSandbox

    sandbox = GitWorktreeSandbox(repo_path=mock_repo, sandbox_id="odd", base_dir=tmp_path / "sb")
    sandbox.create()
    try:
        sandbox.write_file("my file [1].py", b"x = 1\n")
        (sandbox.path / "old.txt").unlink()  # deletion + similar new content must not become a rename
        sandbox.write_file("moved.txt", b"legacy\n")
        patch = sandbox.get_diff()
    finally:
        sandbox.destroy()

    rev = activity_apply_patch(mock_repo, patch, commit_msg="apply odd names")
    changed = set(_git(mock_repo, "show", "--no-renames", "--name-only", "--format=", rev).splitlines())
    assert changed == {"my file [1].py", "old.txt", "moved.txt"}
    assert _git(mock_repo, "status", "--porcelain") == ""


def test_apply_patch_existing_branch_is_clean_error(mock_repo: Path, tmp_path: Path):
    patch = _make_patch(mock_repo, tmp_path, {"calc.py": b"def add(a, b):\n    return a + b\n"})
    current = _git(mock_repo, "rev-parse", "--abbrev-ref", "HEAD")
    with pytest.raises(DarkFactoryError, match="branch"):
        activity_apply_patch(mock_repo, patch, target_branch=current, commit_msg="x")
    assert _git(mock_repo, "status", "--porcelain") == ""


def test_apply_patch_rolls_back_when_commit_fails(mock_repo: Path, tmp_path: Path):
    patch = _make_patch(
        mock_repo,
        tmp_path,
        {"calc.py": b"def add(a, b):\n    return a + b\n", "brand_new.py": b"x = 1\n"},
    )
    original_branch = _git(mock_repo, "rev-parse", "--abbrev-ref", "HEAD")
    original_head = _git(mock_repo, "rev-parse", "HEAD")

    hook = mock_repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho 'rejected by hook' >&2\nexit 1\n")
    hook.chmod(0o755)

    with pytest.raises(DarkFactoryError, match="rejected by hook"):
        activity_apply_patch(mock_repo, patch, target_branch="feature/x", commit_msg="will fail")

    assert _git(mock_repo, "rev-parse", "--abbrev-ref", "HEAD") == original_branch
    assert _git(mock_repo, "rev-parse", "HEAD") == original_head
    assert _git(mock_repo, "branch", "--list", "feature/x") == ""
    assert _git(mock_repo, "status", "--porcelain") == ""
    assert (mock_repo / "calc.py").read_text() == "def add(a, b):\n    return a - b\n"
    assert not (mock_repo / "brand_new.py").exists()


def test_apply_patch_refuses_dirty_target_files(mock_repo: Path, tmp_path: Path):
    patch = _make_patch(mock_repo, tmp_path, {"calc.py": b"def add(a, b):\n    return a + b\n"})
    # Disjoint from the patch hunk, so `git apply --check` alone would happily succeed and the
    # commit would silently swallow the operator's work-in-progress.
    dirty = "def add(a, b):\n    return a - b\n# operator wip\n"
    (mock_repo / "calc.py").write_text(dirty)

    with pytest.raises(DarkFactoryError, match="uncommitted changes"):
        activity_apply_patch(mock_repo, patch, commit_msg="x")

    assert (mock_repo / "calc.py").read_text() == dirty
    assert _git(mock_repo, "log", "--oneline").count("\n") == 0  # still only the baseline commit


class NoOpHarness(AgentHarness):
    """Claims success but rewrites calc.py with identical content (empty diff)."""

    def execute_task(self, sandbox: Sandbox, task_prompt: str, target_files=None):
        sandbox.write_file("calc.py", b"def add(a, b):\n    return a - b\n")
        return HarnessResult(success=True, modified_files=["calc.py"])


def _passing_gate() -> list[VerificationStep]:
    return [VerificationStep(id="ok", argv=[sys.executable, "-c", "raise SystemExit(0)"])]


def test_empty_patch_is_failed_not_awaiting_review(mock_repo: Path, tmp_path: Path):
    engine = DurableEngine(storage_dir=tmp_path / ".factory")
    spec = TaskSpec(repo_path=str(mock_repo), task_prompt="do nothing", verification_steps=_passing_gate())

    manifest = engine.execute_run(spec=spec, harness=NoOpHarness(), run_id="run-noop")

    assert manifest.status == RunStatus.FAILED
    assert "empty patch" in (manifest.operator_notes or "").lower()
    assert engine.list_runs()[0]["status"] == "FAILED"
    with engine._get_connection() as conn:
        payload = conn.execute(
            "SELECT payload FROM events WHERE run_id='run-noop' AND event_type='FAILED';"
        ).fetchone()["payload"]
    assert "empty_patch" in payload
    with pytest.raises(WorkflowStateError):
        engine.review_run("run-noop", approve=True)


class AlwaysSameWrongHarness(AgentHarness):
    """Simulates a model stuck re-deriving the same wrong fix: always writes identical, still-broken code."""

    def execute_task(self, sandbox: Sandbox, task_prompt: str, target_files=None):
        sandbox.write_file("calc.py", b"def add(a, b):\n    return a * b\n")
        return HarnessResult(success=True, modified_files=["calc.py"])


def test_exhausted_healing_notes_repeated_failure(mock_repo: Path, tmp_path: Path):
    """When a run exhausts self-healing because the model kept reproducing the identical failure,
    operator_notes should say so (rather than being left unset, as before this fix)."""
    engine = DurableEngine(storage_dir=tmp_path / ".factory")
    spec = TaskSpec(
        repo_path=str(mock_repo),
        task_prompt="fix add()",
        verification_steps=[VerificationStep(id="pytest", argv=[sys.executable, "-m", "pytest", "test_calc.py"])],
        max_healing_attempts=2,
    )

    manifest = engine.execute_run(spec=spec, harness=AlwaysSameWrongHarness(), run_id="run-stuck")

    assert manifest.status == RunStatus.FAILED
    assert manifest.repeated_failure_streak >= 1
    notes = (manifest.operator_notes or "").lower()
    assert "exhausting" in notes
    assert "repeated identically" in notes
    assert "stuck on one approach" in notes


class DifferentWrongEachTimeHarness(AgentHarness):
    """Simulates a model trying different (still wrong) fixes each attempt — never stuck on one idea."""

    def __init__(self) -> None:
        self.attempt = 0

    def execute_task(self, sandbox: Sandbox, task_prompt: str, target_files=None):
        self.attempt += 1
        # Each attempt is wrong in a different way, so pytest's failure output differs every time. The
        # trailing '#' padding varies the file's byte length per attempt — same-second, same-size rewrites
        # can hit Python's .pyc mtime+size cache and silently re-run stale bytecode (see 10.13's fixture
        # notes on `test_e2e_self_healing_repairs_failing_verification`).
        sandbox.write_file(
            "calc.py", f"def add(a, b):\n    return a + b + {self.attempt}  {'#' * self.attempt}\n".encode()
        )
        return HarnessResult(success=True, modified_files=["calc.py"])


def test_exhausted_healing_notes_different_failures(mock_repo: Path, tmp_path: Path):
    engine = DurableEngine(storage_dir=tmp_path / ".factory")
    spec = TaskSpec(
        repo_path=str(mock_repo),
        task_prompt="fix add()",
        verification_steps=[VerificationStep(id="pytest", argv=[sys.executable, "-m", "pytest", "test_calc.py"])],
        max_healing_attempts=2,
    )

    manifest = engine.execute_run(spec=spec, harness=DifferentWrongEachTimeHarness(), run_id="run-varied-fail")

    assert manifest.status == RunStatus.FAILED
    assert manifest.repeated_failure_streak == 0
    notes = (manifest.operator_notes or "").lower()
    assert "exhausting" in notes
    assert "failed differently" in notes
    assert "stuck" not in notes


def test_run_deadline_ends_timed_out_and_cleans_up(mock_repo: Path, tmp_path: Path):
    import time

    class SlowHarness(MockRepairHarness):
        def execute_task(self, sandbox, task_prompt, target_files=None):
            time.sleep(0.5)
            return super().execute_task(sandbox, task_prompt, target_files)

    storage = tmp_path / ".factory"
    engine = DurableEngine(storage_dir=storage)
    spec = TaskSpec(
        repo_path=str(mock_repo),
        task_prompt="slow",
        verification_steps=_passing_gate(),
        timeout_minutes=0.004,  # ~0.24 s
    )

    manifest = engine.execute_run(spec=spec, harness=SlowHarness(), run_id="run-slow")

    assert manifest.status == RunStatus.TIMED_OUT
    assert engine.list_runs()[0]["status"] == "TIMED_OUT"
    assert engine.get_run("run-slow").status == RunStatus.TIMED_OUT
    assert not (storage / "sandboxes" / "run-slow").exists()
    assert "deadline" in (engine.get_run("run-slow").operator_notes or "").lower()


def test_keyboard_interrupt_ends_cancelled_and_cleans_up(mock_repo: Path, tmp_path: Path):
    class InterruptedHarness(AgentHarness):
        def execute_task(self, sandbox, task_prompt, target_files=None):
            raise KeyboardInterrupt

    storage = tmp_path / ".factory"
    engine = DurableEngine(storage_dir=storage)
    spec = TaskSpec(repo_path=str(mock_repo), task_prompt="x", verification_steps=_passing_gate())

    with pytest.raises(KeyboardInterrupt):
        engine.execute_run(spec=spec, harness=InterruptedHarness(), run_id="run-cancel")

    assert engine.list_runs()[0]["status"] == "CANCELLED"
    assert engine.get_run("run-cancel").status == RunStatus.CANCELLED
    assert not (storage / "sandboxes" / "run-cancel").exists()


def test_evidence_is_persisted_before_awaiting_review_transition(mock_repo: Path, tmp_path: Path):
    engine = DurableEngine(storage_dir=tmp_path / ".factory")
    spec = TaskSpec(repo_path=str(mock_repo), task_prompt="fix", verification_steps=_passing_gate())
    seen: dict = {}

    def on_status(st: RunStatus) -> None:
        if st == RunStatus.AWAITING_REVIEW:
            manifest = engine.locker.load_manifest("run-order")
            seen["sha"] = manifest.patch_sha256
            seen["patch"] = engine.locker.load_patch("run-order")

    engine.execute_run(spec=spec, harness=MockRepairHarness(), run_id="run-order", status_callback=on_status)

    assert seen["sha"] and seen["patch"].strip()


def test_cancelled_run_preserves_partial_diff(mock_repo: Path, tmp_path: Path):
    class WritesThenInterruptsHarness(AgentHarness):
        def execute_task(self, sandbox, task_prompt, target_files=None):
            sandbox.write_file("calc.py", b"def add(a, b):\n    return a + b  # partial fix\n")
            raise KeyboardInterrupt

    storage = tmp_path / ".factory"
    engine = DurableEngine(storage_dir=storage)
    spec = TaskSpec(repo_path=str(mock_repo), task_prompt="x", verification_steps=_passing_gate())

    with pytest.raises(KeyboardInterrupt):
        engine.execute_run(spec=spec, harness=WritesThenInterruptsHarness(), run_id="run-cancel-diff")

    manifest = engine.get_run("run-cancel-diff")
    assert manifest.status == RunStatus.CANCELLED
    assert manifest.patch_size_bytes > 0
    patch = engine.locker.load_patch("run-cancel-diff")
    assert "partial fix" in patch


def test_recover_flags_approved_transition_that_never_completed(mock_repo: Path, tmp_path: Path):
    """Simulate a crash between `transition_status(APPROVED)` and the final `locker.save_run()`."""
    engine = DurableEngine(storage_dir=tmp_path / ".factory")
    spec = TaskSpec(repo_path=str(mock_repo), task_prompt="fix", verification_steps=_passing_gate())
    engine.execute_run(spec=spec, harness=MockRepairHarness(), run_id="run-approve-crash")

    # DB says APPROVED, but the on-disk manifest never caught up (still AWAITING_REVIEW, no resulting_rev).
    with engine._get_connection() as conn:
        conn.execute("UPDATE runs SET status='APPROVED' WHERE run_id='run-approve-crash';")

    recovered = engine.recover()

    assert "run-approve-crash" in recovered
    with engine._get_connection() as conn:
        row = conn.execute("SELECT status FROM runs WHERE run_id='run-approve-crash';").fetchone()
    assert row["status"] == "FAILED"


def test_recover_leaves_genuinely_completed_approval_alone(mock_repo: Path, tmp_path: Path):
    engine = DurableEngine(storage_dir=tmp_path / ".factory")
    spec = TaskSpec(repo_path=str(mock_repo), task_prompt="fix", verification_steps=_passing_gate())
    engine.execute_run(spec=spec, harness=MockRepairHarness(), run_id="run-approve-ok")
    engine.review_run(run_id="run-approve-ok", approve=True, target_branch="feature/ok")

    recovered = engine.recover()

    assert "run-approve-ok" not in recovered
    with engine._get_connection() as conn:
        row = conn.execute("SELECT status FROM runs WHERE run_id='run-approve-ok';").fetchone()
    assert row["status"] == "APPROVED"


def test_execute_run_records_phase_timings(mock_repo: Path, tmp_path: Path):
    engine = DurableEngine(storage_dir=tmp_path / ".factory")
    spec = TaskSpec(repo_path=str(mock_repo), task_prompt="fix", verification_steps=_passing_gate())

    manifest = engine.execute_run(spec=spec, harness=MockRepairHarness(), run_id="run-phase-timings")

    phases = {pt.phase for pt in manifest.phase_timings}
    assert phases == {"sandbox_create", "agent_and_verify", "diff_extract", "evidence_preserve"}
    assert all(pt.duration_sec >= 0 for pt in manifest.phase_timings)
    assert all(pt.started_at for pt in manifest.phase_timings)

    # Round-trips through the evidence locker like the rest of the manifest.
    reloaded = engine.get_run("run-phase-timings")
    assert {pt.phase for pt in reloaded.phase_timings} == phases


def test_timed_out_run_records_phase_timings(mock_repo: Path, tmp_path: Path):
    import time

    class SlowHarness(MockRepairHarness):
        def execute_task(self, sandbox, task_prompt, target_files=None):
            time.sleep(0.3)
            return super().execute_task(sandbox, task_prompt, target_files)

    engine = DurableEngine(storage_dir=tmp_path / ".factory")
    spec = TaskSpec(
        repo_path=str(mock_repo),
        task_prompt="slow",
        verification_steps=_passing_gate(),
        timeout_minutes=0.002,  # ~0.12s
    )

    manifest = engine.execute_run(spec=spec, harness=SlowHarness(), run_id="run-phase-timings-timeout")

    phases = {pt.phase for pt in manifest.phase_timings}
    assert phases == {"sandbox_create", "agent_and_verify", "evidence_preserve"}


def test_cancelled_run_records_phase_timings(mock_repo: Path, tmp_path: Path):
    class InterruptedHarness(AgentHarness):
        def execute_task(self, sandbox, task_prompt, target_files=None):
            raise KeyboardInterrupt

    engine = DurableEngine(storage_dir=tmp_path / ".factory")
    spec = TaskSpec(repo_path=str(mock_repo), task_prompt="x", verification_steps=_passing_gate())

    with pytest.raises(KeyboardInterrupt):
        engine.execute_run(spec=spec, harness=InterruptedHarness(), run_id="run-phase-timings-cancel")

    manifest = engine.get_run("run-phase-timings-cancel")
    phases = {pt.phase for pt in manifest.phase_timings}
    assert "sandbox_create" in phases
    assert "evidence_preserve" in phases


def test_review_run_approve_records_patch_apply_phase_timing(mock_repo: Path, tmp_path: Path):
    engine = DurableEngine(storage_dir=tmp_path / ".factory")
    spec = TaskSpec(repo_path=str(mock_repo), task_prompt="fix", verification_steps=_passing_gate())
    engine.execute_run(spec=spec, harness=MockRepairHarness(), run_id="run-phase-timings-apply")

    approved = engine.review_run(run_id="run-phase-timings-apply", approve=True, target_branch="feature/x")

    apply_timings = [pt for pt in approved.phase_timings if pt.phase == "patch_apply"]
    assert len(apply_timings) == 1
    assert apply_timings[0].duration_sec >= 0


def test_recover_promotes_run_whose_evidence_completed_before_crash(mock_repo: Path, tmp_path: Path):
    engine = DurableEngine(storage_dir=tmp_path / ".factory")
    spec = TaskSpec(repo_path=str(mock_repo), task_prompt="fix", verification_steps=_passing_gate())
    engine.execute_run(spec=spec, harness=MockRepairHarness(), run_id="run-crash-window")

    # Simulate a crash between "evidence saved" and "DB transition to AWAITING_REVIEW".
    with engine._get_connection() as conn:
        conn.execute("UPDATE runs SET status='VERIFYING' WHERE run_id='run-crash-window';")

    recovered = engine.recover()

    assert "run-crash-window" in recovered
    assert engine.list_runs()[0]["status"] == "AWAITING_REVIEW"
    approved = engine.review_run("run-crash-window", approve=True)
    assert approved.status == RunStatus.APPROVED


class _MarkedHarness(AgentHarness):
    """Writes a file whose name/content embed a unique per-run marker, so concurrent runs can be checked
    for cross-contamination (one run's output leaking into another's patch/manifest)."""

    def __init__(self, marker: str) -> None:
        self.marker = marker

    def execute_task(self, sandbox: Sandbox, task_prompt: str, target_files=None):
        sandbox.write_file(f"feature_{self.marker}.py", f"# {self.marker}\nvalue = {self.marker!r}\n".encode())
        return HarnessResult(success=True, modified_files=[f"feature_{self.marker}.py"])


def test_concurrent_execute_run_isolated_sandboxes(mock_repo: Path, tmp_path: Path):
    """N runs in flight at once against one DurableEngine/one repo: each gets its own GitWorktreeSandbox,
    so this is a concurrency smoke test for that isolation, plus SQLite (WAL) surviving concurrent writes."""
    engine = DurableEngine(storage_dir=tmp_path / ".factory")
    n = 8

    def run_one(i: int):
        marker = f"run{i}"
        spec = TaskSpec(repo_path=str(mock_repo), task_prompt="add feature", verification_steps=_passing_gate())
        return engine.execute_run(spec=spec, harness=_MarkedHarness(marker), run_id=f"run-load-{i}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=n) as pool:
        results = list(pool.map(run_one, range(n)))

    assert all(m.status == RunStatus.AWAITING_REVIEW for m in results)
    assert {m.run_id for m in results} == {f"run-load-{i}" for i in range(n)}

    for i, manifest in enumerate(results):
        patch = engine.locker.load_patch(manifest.run_id)
        assert f"run{i}" in patch
        for j in range(n):
            if j != i:
                assert f"run{j}" not in patch  # no cross-contamination between concurrent sandboxes

    with engine._get_connection() as conn:
        rows = conn.execute("SELECT status FROM runs;").fetchall()
    assert len(rows) == n
    assert all(r["status"] == "AWAITING_REVIEW" for r in rows)


def test_concurrent_review_run_serializes_git_mutations(mock_repo: Path, tmp_path: Path):
    """Unlike sandboxes, `activity_apply_patch` mutates the host repo's actual working tree directly
    (checkout/apply/commit). Approving N runs at once against the *same* repo is a genuine
    shared-mutable-state hazard; `DurableEngine._review_lock` must serialize it so N concurrent approvals
    still produce N clean, distinct commits instead of a corrupted working tree or lost commits."""
    engine = DurableEngine(storage_dir=tmp_path / ".factory")
    n = 8
    run_ids = [f"run-review-load-{i}" for i in range(n)]

    for i, run_id in enumerate(run_ids):
        spec = TaskSpec(repo_path=str(mock_repo), task_prompt="add feature", verification_steps=_passing_gate())
        engine.execute_run(spec=spec, harness=_MarkedHarness(f"run{i}"), run_id=run_id)

    def approve_one(run_id: str):
        return engine.review_run(run_id=run_id, approve=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=n) as pool:
        results = list(pool.map(approve_one, run_ids))

    assert all(m.status == RunStatus.APPROVED for m in results)

    log = subprocess.run(["git", "log", "--oneline"], cwd=mock_repo, check=True, capture_output=True, text=True).stdout
    assert log.count("\n") == n + 1  # baseline commit + one per approved run, nothing lost or merged wrong

    for i in range(n):
        assert (mock_repo / f"feature_run{i}.py").exists()

    status = subprocess.run(["git", "status", "--porcelain"], cwd=mock_repo, capture_output=True, text=True)
    assert status.stdout.strip() == ""
