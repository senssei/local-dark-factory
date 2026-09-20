"""Unit tests for GitWorktreeSandbox."""

import subprocess
from pathlib import Path

import pytest

from dark_factory.domain.errors import SandboxError, WorktreeCreationError
from dark_factory.sandbox import GitWorktreeSandbox


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository for testing worktree isolation."""
    repo = tmp_path / "test_repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True, capture_output=True)

    # Initial commit
    (repo / "hello.py").write_text("print('hello baseline')\n")
    subprocess.run(["git", "add", "hello.py"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=repo, check=True, capture_output=True)
    return repo


def test_worktree_lifecycle(temp_git_repo: Path, tmp_path: Path):
    sandbox_base = tmp_path / "sandboxes"
    sandbox = GitWorktreeSandbox(
        repo_path=temp_git_repo,
        sandbox_id="run-test-01",
        base_dir=sandbox_base,
    )

    # Create
    sandbox.create(base_rev="HEAD")
    assert sandbox.path.exists()
    assert (sandbox.path / "hello.py").exists()

    # Execute command
    res = sandbox.execute(["python3", "hello.py"])
    assert res.passed
    assert "hello baseline" in res.stdout

    # Write new file & modify existing
    sandbox.write_file("new_file.txt", b"new content\n")
    assert sandbox.read_file("new_file.txt") == b"new content\n"

    sandbox.write_file("hello.py", b"print('hello modified')\n")

    # Get diff
    diff = sandbox.get_diff()
    assert "new_file.txt" in diff
    assert "hello modified" in diff

    # Destroy
    sandbox.destroy()
    assert not sandbox.path.exists()

    # Destroy idempotency
    sandbox.destroy()


def test_worktree_timeout(temp_git_repo: Path, tmp_path: Path):
    sandbox = GitWorktreeSandbox(
        repo_path=temp_git_repo,
        sandbox_id="run-test-timeout",
        base_dir=tmp_path / "sandboxes",
    )
    sandbox.create()

    try:
        # Sleep for 3 seconds with a 1 second timeout
        res = sandbox.execute(["python3", "-c", "import time; time.sleep(3)"], timeout=1)
        assert not res.passed
        assert res.timed_out
    finally:
        sandbox.destroy()


def test_worktree_path_traversal(temp_git_repo: Path, tmp_path: Path):
    sandbox = GitWorktreeSandbox(
        repo_path=temp_git_repo,
        sandbox_id="run-test-traversal",
        base_dir=tmp_path / "sandboxes",
    )
    sandbox.create()

    try:
        with pytest.raises(SandboxError, match="Path traversal detected"):
            sandbox.write_file("../forbidden.txt", b"evil")

        with pytest.raises(SandboxError, match="Path traversal detected"):
            sandbox.read_file("../../etc/passwd")
    finally:
        sandbox.destroy()


def test_worktree_invalid_repo(tmp_path: Path):
    invalid_dir = tmp_path / "not_a_repo"
    invalid_dir.mkdir()

    sandbox = GitWorktreeSandbox(
        repo_path=invalid_dir,
        sandbox_id="fail",
    )
    with pytest.raises(WorktreeCreationError):
        sandbox.create()
