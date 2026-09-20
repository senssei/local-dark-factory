"""Unit tests for DurableEngine and state orchestration."""

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
