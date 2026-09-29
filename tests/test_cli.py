"""Unit tests for dark_factory.cli."""

import subprocess
import time
from pathlib import Path

import dark_factory.cli as cli_module
from dark_factory.cli import main
from dark_factory.harness.base import AgentHarness, HarnessResult


def test_cli_doctor():
    res = main(["doctor"])
    assert res == 0


def test_cli_list_empty(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = main(["list"])
    assert res == 0


def test_cli_review_invalid_args():
    res = main(["review", "run-fake"])
    assert res == 1


def test_cli_describe_not_found(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = main(["describe", "run-nonexistent"])
    assert res == 1


def test_cli_run_without_gates_fails(tmp_path: Path, capsys):
    empty_repo = tmp_path / "empty_repo"
    empty_repo.mkdir()
    res = main(["run", "--repo", str(empty_repo), "--task", "Implement feature"])
    assert res == 1
    captured = capsys.readouterr()
    assert "No verification gates configured" in captured.err


def test_cli_run_nonexistent_repo(capsys):
    res = main(["run", "--repo", "/path/that/does/not/exist", "--task", "Foo"])
    assert res == 1
    captured = capsys.readouterr()
    assert "Repository path does not exist" in captured.err


def test_cli_run_respects_timeout_minutes_and_storage_dir(tmp_path: Path, monkeypatch):
    """Regression for the 10.7/10.8 CLI flags: --timeout-minutes must actually reach TaskSpec, and
    --storage-dir must actually reach DurableEngine, not just be accepted by argparse."""

    class SlowHarness(AgentHarness):
        def execute_task(self, sandbox, task_prompt, target_files=None):
            time.sleep(0.5)
            sandbox.write_file("x.txt", b"x")
            return HarnessResult(success=True, modified_files=["x.txt"])

    monkeypatch.setattr(cli_module, "LocalCoderHarness", lambda **kwargs: SlowHarness())

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "CLI Test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "cli@test.local"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True, capture_output=True)
    (repo / "readme.txt").write_text("baseline\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=repo, check=True, capture_output=True)

    storage = tmp_path / "custom-journal"
    res = main(
        [
            "run",
            "--repo",
            str(repo),
            "--task",
            "slow task",
            "--no-verify",
            "--timeout-minutes",
            "0.004",  # ~0.24s, shorter than SlowHarness's 0.5s sleep
            "--storage-dir",
            str(storage),
        ]
    )

    assert res == 1  # TIMED_OUT is not AWAITING_REVIEW
    assert storage.exists()  # proves --storage-dir was actually wired, not just parsed


def test_cli_describe_prints_phase_timings(tmp_path: Path, monkeypatch, capsys):
    class FastHarness(AgentHarness):
        def execute_task(self, sandbox, task_prompt, target_files=None):
            sandbox.write_file("x.txt", b"x")
            return HarnessResult(success=True, modified_files=["x.txt"])

    monkeypatch.setattr(cli_module, "LocalCoderHarness", lambda **kwargs: FastHarness())

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "CLI Test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "cli@test.local"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True, capture_output=True)
    (repo / "readme.txt").write_text("baseline\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=repo, check=True, capture_output=True)

    storage = tmp_path / ".factory"
    res = main(
        [
            "run",
            "--repo",
            str(repo),
            "--task",
            "fast task",
            "--no-verify",
            "--storage-dir",
            str(storage),
        ]
    )
    assert res == 0

    run_id = next(
        line.split(":", 1)[1].strip()
        for line in capsys.readouterr().out.splitlines()
        if line.strip().startswith("🏁 RUN FINISHED")
    )

    res = main(["describe", run_id, "--storage-dir", str(storage)])
    assert res == 0
    out = capsys.readouterr().out
    assert "--- PHASE TIMINGS ---" in out
    assert "[sandbox_create]" in out
    assert "[agent_and_verify]" in out


def test_cli_eval_list(capsys):
    res = main(["eval", "--list"])
    assert res == 0
    out = capsys.readouterr().out
    assert "primes" in out
    assert "calculator" in out
    assert "textutils" in out
    assert "csvparse" in out


def test_cli_eval_unknown_scenario(capsys):
    res = main(["eval", "--scenario", "nope"])
    assert res == 1
    err = capsys.readouterr().err
    assert "unknown scenario" in err.lower()
    assert "nope" in err


def test_cli_eval_no_local_engine_short_circuits(monkeypatch, capsys):
    monkeypatch.setattr(cli_module.LocalCoderHarness, "check_health", lambda self: {"ollama": False, "prism": False})
    res = main(["eval", "--scenario", "primes"])
    assert res == 1
    err = capsys.readouterr().err
    assert "no local inference engine" in err.lower()


def test_cli_dashboard_wires_args_through(monkeypatch, tmp_path: Path):
    import dark_factory.dashboard as dashboard_module

    calls = {}

    def fake_run_dashboard(storage_dir, port, open_browser):
        calls["storage_dir"] = storage_dir
        calls["port"] = port
        calls["open_browser"] = open_browser

    monkeypatch.setattr(dashboard_module, "run_dashboard", fake_run_dashboard)

    res = main(["dashboard", "--port", "9999", "--no-browser", "--storage-dir", str(tmp_path / ".factory")])

    assert res == 0
    assert calls["port"] == 9999
    assert calls["open_browser"] is False
    assert calls["storage_dir"] == tmp_path / ".factory"
