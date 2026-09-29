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


def test_worktree_restore_paths(temp_git_repo: Path, tmp_path: Path):
    sandbox = GitWorktreeSandbox(
        repo_path=temp_git_repo,
        sandbox_id="run-test-restore",
        base_dir=tmp_path / "sandboxes",
    )
    sandbox.create()

    try:
        # 1. Modify an existing tracked file hello.py
        sandbox.write_file("hello.py", b"print('tampered')\n")
        # 2. Add an untracked file inside tests/
        sandbox.write_file("tests/fake_test.py", b"assert True\n")

        # Restore hello.py and tests
        restored = sandbox.restore_paths(["hello.py", "tests"])
        assert "hello.py" in restored
        assert "tests" in restored

        # Check that hello.py is restored to original
        assert sandbox.read_file("hello.py") == b"print('hello baseline')\n"

        # Check that untracked tests/fake_test.py was removed
        assert not (sandbox.path / "tests" / "fake_test.py").exists()

        # If we run restore again when nothing is tampered, it should return empty list
        restored_again = sandbox.restore_paths(["hello.py", "tests"])
        assert restored_again == []
    finally:
        sandbox.destroy()


@pytest.mark.parametrize("bad_path", [".git", ".git/config", "sub/.git", "./.git"])
def test_worktree_rejects_writes_to_git_metadata(temp_git_repo: Path, tmp_path: Path, bad_path: str):
    sandbox = GitWorktreeSandbox(
        repo_path=temp_git_repo,
        sandbox_id="run-test-dotgit",
        base_dir=tmp_path / "sandboxes",
    )
    sandbox.create()
    try:
        original = (sandbox.path / ".git").read_bytes()
        with pytest.raises(SandboxError, match=r"\.git"):
            sandbox.write_file(bad_path, b"gitdir: /somewhere/else\n")
        # The worktree pointer must be untouched.
        assert (sandbox.path / ".git").read_bytes() == original
    finally:
        sandbox.destroy()


def test_worktree_allows_gitignore_like_names(temp_git_repo: Path, tmp_path: Path):
    sandbox = GitWorktreeSandbox(
        repo_path=temp_git_repo,
        sandbox_id="run-test-gitignore",
        base_dir=tmp_path / "sandboxes",
    )
    sandbox.create()
    try:
        sandbox.write_file(".gitignore", b"*.log\n")
        sandbox.write_file(".github/workflows/ci.yml", b"name: ci\n")
        assert sandbox.read_file(".gitignore") == b"*.log\n"
    finally:
        sandbox.destroy()


def test_get_diff_ignores_user_git_config(temp_git_repo: Path, tmp_path: Path):
    """diff.noprefix / color.ui / binary files must not corrupt the stored patch."""
    subprocess.run(["git", "config", "diff.noprefix", "true"], cwd=temp_git_repo, check=True)
    subprocess.run(["git", "config", "color.ui", "always"], cwd=temp_git_repo, check=True)
    subprocess.run(["git", "config", "diff.mnemonicPrefix", "true"], cwd=temp_git_repo, check=True)

    sandbox = GitWorktreeSandbox(
        repo_path=temp_git_repo,
        sandbox_id="run-test-diffcfg",
        base_dir=tmp_path / "sandboxes",
    )
    sandbox.create()
    try:
        sandbox.write_file("hello.py", b"print('changed')\n")
        sandbox.write_file("blob.bin", bytes(range(256)))
        diff = sandbox.get_diff()

        assert "diff --git a/hello.py b/hello.py" in diff
        assert "diff --git a/blob.bin b/blob.bin" in diff
        assert "\x1b[" not in diff
        assert "GIT binary patch" in diff

        # The patch must apply cleanly to the pristine baseline.
        check = subprocess.run(
            ["git", "apply", "--check", "-"], cwd=temp_git_repo, input=diff, text=True, capture_output=True
        )
        assert check.returncode == 0, check.stderr
    finally:
        sandbox.destroy()


def test_get_diff_raises_when_git_fails(temp_git_repo: Path, tmp_path: Path):
    sandbox = GitWorktreeSandbox(
        repo_path=temp_git_repo,
        sandbox_id="run-test-diffbroken",
        base_dir=tmp_path / "sandboxes",
    )
    sandbox.create()
    try:
        (sandbox.path / ".git").unlink()  # sandbox is no longer a valid worktree
        with pytest.raises(SandboxError, match="git diff"):
            sandbox.get_diff()
    finally:
        sandbox.destroy()


def test_restore_paths_glob_covers_nested_conftest(temp_git_repo: Path, tmp_path: Path):
    sandbox = GitWorktreeSandbox(
        repo_path=temp_git_repo,
        sandbox_id="run-test-glob",
        base_dir=tmp_path / "sandboxes",
    )
    sandbox.create()
    try:
        sandbox.write_file("conftest.py", b"collect_ignore_glob = ['*']\n")
        sandbox.write_file("pkg/sub/conftest.py", b"collect_ignore_glob = ['*']\n")
        restored = sandbox.restore_paths([":(glob)**/conftest.py"])
        assert restored == [":(glob)**/conftest.py"]
        assert not (sandbox.path / "conftest.py").exists()
        assert not (sandbox.path / "pkg" / "sub" / "conftest.py").exists()
    finally:
        sandbox.destroy()
