from __future__ import annotations

import py_compile
import subprocess
import sys
from pathlib import Path

import pytest

from dark_factory.domain.types import VerificationStep
from dark_factory.sandbox import GitWorktreeSandbox
from dark_factory.verification import VerificationRunner


@pytest.mark.parametrize(
    "shadow, custom_protection",
    [
        ("pytest.py", False),
        ("pytest/__init__.py", False),
        ("pytest.pyc", False),
        ("_pytest/__init__.py", False),
        ("pluggy.py", False),
        ("unittest.py", False),
        ("pytest.py", True),
        ("pytest/__init__.py", True),
        ("pytest.pyc", True),
        ("_pytest/__init__.py", True),
        ("pluggy.py", True),
        ("unittest.py", True),
    ],
)
def test_runner_shadow_cannot_pass(tmp_path: Path, shadow: str, custom_protection: bool) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", repo, "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", repo, "config", "user.name", "test"], check=True, capture_output=True)
    subprocess.run(["git", "-C", repo, "config", "user.email", "test@example.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", repo, "config", "commit.gpgsign", "false"], check=True, capture_output=True)
    (repo / "tests").mkdir()
    with open(repo / "tests" / "test_fail.py", "w") as f:
        f.write(
            "import unittest\n\nclass TestVerificationRunner(unittest.TestCase):\n    def test_fail(self):\n        self.assertTrue(False)"
            if shadow == "unittest.py"
            else "def test_fail(): assert False"
        )
    with open(repo / ".gitignore", "w") as f:
        f.write("pytest.py\npytest/\n*.pyc\n_pytest/\npluggy.py\nunittest.py\n.venv/\n")
    subprocess.run(["git", "-C", repo, "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", repo, "commit", "-m", "Initial commit"], check=True, capture_output=True)

    sandbox = GitWorktreeSandbox(repo, "shadow", base_dir=tmp_path / "sandboxes")
    try:
        sandbox.create()
        sandbox.write_file(".venv/keep", b"keep")
        if shadow == "pytest.pyc":
            sandbox.write_file("pytest.py", b'print("SHADOW_EXECUTED")\n')
            py_compile.compile(str(sandbox.path / "pytest.py"), cfile=str(sandbox.path / "pytest.pyc"))
            (sandbox.path / "pytest.py").unlink()
        else:
            sandbox.write_file(shadow, b'print("SHADOW_EXECUTED")\nraise SystemExit(0)\n')
        outcome = VerificationRunner(
            [
                VerificationStep(
                    "test",
                    [sys.executable, "-m", "pytest", "tests", "-q"]
                    if shadow != "unittest.py"
                    else [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                )
            ],
            protected_paths=["tests"] if custom_protection else None,
        ).run(sandbox)
        if shadow == "unittest.py":
            assert not outcome.passed
            assert "FAILED" in outcome.executions[0].stderr
        else:
            assert not outcome.passed
            assert "1 failed" in outcome.executions[0].stdout
            assert "SHADOW_EXECUTED" not in outcome.executions[0].stdout
        assert sandbox.read_file(".venv/keep") == b"keep"
    finally:
        sandbox.destroy()


def test_detect_runner_paths() -> None:
    paths = VerificationRunner([VerificationStep("test", ["python3", "-m", "dotted.module"])]).detect_runner_paths()
    assert set(paths) == {"dotted", "dotted.py", "dotted.pyc", ":(glob)__pycache__/dotted.*.pyc"}


def test_ruff_console_command() -> None:
    runner = VerificationRunner([VerificationStep("lint", ["ruff", "check", "calc.py"])])
    assert "ruff.py" in runner.detect_runner_paths()
    assert "calc.py" not in runner.detect_default_gate_paths()


def test_restore_failure() -> None:
    from unittest.mock import MagicMock

    from dark_factory.domain.errors import SandboxError

    sandbox = MagicMock(spec=GitWorktreeSandbox)
    sandbox.restore_paths.return_value = []
    sandbox.restore_runner_paths.side_effect = SandboxError("restore failed")
    runner = VerificationRunner([VerificationStep("test", [sys.executable, "-m", "pytest"])])
    with pytest.raises(SandboxError, match="restore failed"):
        runner.run(sandbox)
    sandbox.execute.assert_not_called()


def test_allow_gate_edits() -> None:
    from unittest.mock import MagicMock

    from dark_factory.domain.types import StepExecution

    sandbox = MagicMock(spec=GitWorktreeSandbox)
    sandbox.execute.return_value = StepExecution("test", 0, "", "", 0)
    runner = VerificationRunner([VerificationStep("test", [sys.executable, "-m", "pytest"])], allow_gate_edits=True)
    assert runner.run(sandbox).passed
    sandbox.restore_paths.assert_not_called()
    sandbox.restore_runner_paths.assert_not_called()


def test_edited_application_is_verified(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True, capture_output=True)

    tests = repo / "tests"
    tests.mkdir()
    (repo / "app.py").write_text("answer = 1")
    (tests / "test_app.py").write_text("from app import answer\ndef test_app(): assert answer == 2\n")

    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo, check=True, capture_output=True)

    sandbox = GitWorktreeSandbox(repo, "app", base_dir=tmp_path / "sandboxes")
    try:
        sandbox.create()
        (sandbox.path / "app.py").write_text("answer = 2")
        with open(sandbox.path / "pytest.py", "w") as f:
            f.write('print("SHADOW_EXECUTED")')

        outcome = VerificationRunner([VerificationStep("test", [sys.executable, "-m", "pytest", "tests", "-q"])]).run(
            sandbox
        )
        assert (
            outcome.passed
            and "1 passed" in outcome.executions[0].stdout
            and "SHADOW_EXECUTED" not in outcome.executions[0].stdout
        )
        assert (sandbox.path / "app.py").read_text() == "answer = 2"
    finally:
        sandbox.destroy()
