"""Git worktree-based sandbox implementation for Sovereign Dark Factory."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

from dark_factory.domain.errors import (
    SandboxError,
    WorktreeCreationError,
)
from dark_factory.domain.types import StepExecution
from dark_factory.sandbox.base import Sandbox


class GitWorktreeSandbox(Sandbox):
    """A lightweight, isolated sandbox using git worktrees (<100ms startup)."""

    def __init__(
        self,
        repo_path: str | Path,
        sandbox_id: str,
        base_dir: str | Path | None = None,
    ) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.sandbox_id = sandbox_id
        if base_dir is None:
            self.sandbox_dir = (self.repo_path / ".factory" / "sandboxes" / sandbox_id).resolve()
        else:
            self.sandbox_dir = (Path(base_dir).resolve() / sandbox_id).resolve()
        self._created = False
        self._base_sha: str | None = None

    @property
    def path(self) -> Path:
        return self.sandbox_dir

    def create(self, base_rev: str = "HEAD") -> None:
        """Create an isolated git worktree at the given revision."""
        if self._created:
            return

        if not (self.repo_path / ".git").exists() and not self._is_git_repo():
            raise WorktreeCreationError(f"Target path is not a git repository: {self.repo_path}")

        # Resolve commit SHA
        try:
            rev_res = subprocess.run(
                ["git", "rev-parse", base_rev],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            self._base_sha = rev_res.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise WorktreeCreationError(f"Failed to resolve revision '{base_rev}': {e.stderr}") from e

        # Ensure parent directory exists
        self.sandbox_dir.parent.mkdir(parents=True, exist_ok=True)

        # Create worktree
        cmd = ["git", "worktree", "add", "--detach", str(self.sandbox_dir), self._base_sha]
        try:
            subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            self._created = True
        except subprocess.CalledProcessError as e:
            raise WorktreeCreationError(f"Failed to create git worktree at {self.sandbox_dir}: {e.stderr}") from e

    def execute(
        self,
        argv: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int = 300,
        step_id: str = "exec",
    ) -> StepExecution:
        """Execute a command inside the sandbox."""
        if not self._created:
            raise SandboxError("Sandbox has not been created yet.")

        target_cwd = self.sandbox_dir if cwd is None else (self.sandbox_dir / cwd).resolve()
        self._check_path_within_sandbox(target_cwd)

        # Build clean environment
        exec_env = os.environ.copy()
        # Strip git and python env vars that might leak from parent/outer runtime
        for key in ["GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "VIRTUAL_ENV", "PYTHONPATH"]:
            exec_env.pop(key, None)
        if env:
            exec_env.update(env)

        start_time = time.monotonic()
        timed_out = False

        try:
            process = subprocess.Popen(
                argv,
                cwd=target_cwd,
                env=exec_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = process.communicate(timeout=timeout)
            exit_code = process.returncode
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            exit_code = -1
            timed_out = True
        except Exception as e:
            duration = time.monotonic() - start_time
            return StepExecution(
                step_id=step_id,
                exit_code=1,
                stdout="",
                stderr=f"Execution error: {e}",
                duration_sec=duration,
                timed_out=False,
            )

        duration = time.monotonic() - start_time
        return StepExecution(
            step_id=step_id,
            exit_code=exit_code,
            stdout=stdout or "",
            stderr=stderr or "",
            duration_sec=duration,
            timed_out=timed_out,
        )

    def read_file(self, rel_path: str) -> bytes:
        """Read a file relative to sandbox root."""
        if not self._created:
            raise SandboxError("Sandbox has not been created yet.")
        target_file = (self.sandbox_dir / rel_path).resolve()
        self._check_path_within_sandbox(target_file)
        if not target_file.is_file():
            raise FileNotFoundError(f"File not found in sandbox: {rel_path}")
        return target_file.read_bytes()

    def write_file(self, rel_path: str, content: bytes) -> None:
        """Write a file relative to sandbox root, creating parent directories."""
        if not self._created:
            raise SandboxError("Sandbox has not been created yet.")
        target_file = (self.sandbox_dir / rel_path).resolve()
        self._check_path_within_sandbox(target_file)
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_bytes(content)

    def get_diff(self) -> str:
        """Extract unified git diff of all modifications including untracked files."""
        if not self._created:
            raise SandboxError("Sandbox has not been created yet.")

        # Clean python bytecode and test caches if any were generated
        try:
            for pyc in self.sandbox_dir.rglob("*.pyc"):
                pyc.unlink(missing_ok=True)
            for cache_dir in list(self.sandbox_dir.rglob("__pycache__")):
                if cache_dir.is_dir():
                    shutil.rmtree(cache_dir, ignore_errors=True)
            for cache_dir in list(self.sandbox_dir.rglob(".pytest_cache")):
                if cache_dir.is_dir():
                    shutil.rmtree(cache_dir, ignore_errors=True)
        except Exception:
            pass

        # Stage untracked files intent-to-add so diff captures new files too
        subprocess.run(
            ["git", "add", "-N", "."],
            cwd=self.sandbox_dir,
            capture_output=True,
            text=True,
        )

        diff_res = subprocess.run(
            [
                "git",
                "diff",
                "HEAD",
                "--",
                ".",
                ":(exclude)__pycache__",
                ":(exclude)*.pyc",
                ":(exclude).pytest_cache",
            ],
            cwd=self.sandbox_dir,
            capture_output=True,
            text=True,
        )
        return diff_res.stdout

    def restore_paths(self, paths: list[str], rev: str | None = None) -> list[str]:
        """Restore specified paths to their baseline state at the given revision.

        Returns the list of paths that were actually modified and restored.
        """
        if not self._created:
            raise SandboxError("Sandbox has not been created yet.")
        if not paths:
            return []

        target_rev = rev or self._base_sha or "HEAD"
        restored: list[str] = []

        for p in paths:
            rel = p.lstrip("/")
            # 1. Check if git reports modifications, deletions, or staged changes for path
            diff_res = subprocess.run(
                ["git", "diff", target_rev, "--name-only", "--", rel],
                cwd=self.sandbox_dir,
                capture_output=True,
                text=True,
            )
            # 2. Check for untracked new files under path
            untracked_res = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard", "--", rel],
                cwd=self.sandbox_dir,
                capture_output=True,
                text=True,
            )
            has_diff = bool(diff_res.stdout.strip())
            has_untracked = bool(untracked_res.stdout.strip())

            if has_diff or has_untracked:
                # Restore tracked files to target_rev
                subprocess.run(
                    ["git", "checkout", target_rev, "--", rel],
                    cwd=self.sandbox_dir,
                    capture_output=True,
                    text=True,
                )
                # Clean untracked files
                subprocess.run(
                    ["git", "clean", "-fd", "--", rel],
                    cwd=self.sandbox_dir,
                    capture_output=True,
                    text=True,
                )
                restored.append(rel)

        return restored

    def destroy(self) -> None:
        """Destroy the worktree and clean up files idempotently."""
        if not self._created and not self.sandbox_dir.exists():
            return

        # Tell git to remove worktree
        try:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(self.sandbox_dir)],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            pass

        # Cleanup directory if still exists
        if self.sandbox_dir.exists():
            shutil.rmtree(self.sandbox_dir, ignore_errors=True)

        # Prune dead worktrees
        try:
            subprocess.run(
                ["git", "worktree", "prune"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            pass

        self._created = False

    def _is_git_repo(self) -> bool:
        res = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )
        return res.returncode == 0

    def _check_path_within_sandbox(self, path: Path) -> None:
        try:
            path.relative_to(self.sandbox_dir)
        except ValueError:
            raise SandboxError(f"Path traversal detected outside sandbox: {path}") from None
