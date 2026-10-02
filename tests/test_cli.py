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


def test_cli_run_passes_no_adversarial_flag(tmp_path: Path, monkeypatch):
    from dark_factory.domain.types import EvidenceManifest, RunStatus
    from dark_factory.orchestrator import DurableEngine

    captured_specs = []

    def mock_execute_run(self, spec, harness=None, run_id=None, status_callback=None):
        captured_specs.append(spec)
        manifest = EvidenceManifest.create(run_id="run-test", repo_path=spec.repo_path, base_rev=spec.base_rev)
        manifest.status = RunStatus.AWAITING_REVIEW
        return manifest

    monkeypatch.setattr(DurableEngine, "execute_run", mock_execute_run)

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "test.sh").write_text("#!/bin/sh\nexit 0\n")

    res = main(["run", "--repo", str(repo), "--task", "Foo", "--no-adversarial"])
    assert res == 0
    assert len(captured_specs) == 1
    assert captured_specs[0].skip_adversarial is True


def test_cli_describe_renders_adversarial_report(tmp_path: Path, capsys):
    from dark_factory.domain.types import AdversarialFinding, AdversarialReport, EvidenceManifest, RunStatus
    from dark_factory.storage import EvidenceLocker

    storage = tmp_path / ".factory"
    locker = EvidenceLocker(storage_dir=storage)
    manifest = EvidenceManifest.create(run_id="run-adv-test", repo_path="/tmp/repo", base_rev="abc1234")
    manifest.status = RunStatus.AWAITING_REVIEW
    manifest.adversarial_report = AdversarialReport(
        passed=False,
        summary="Found critical cheating pattern.",
        findings=[
            AdversarialFinding(
                severity="CRITICAL",
                category="anti-cheating",
                summary="Hardcoded return value",
                details="Function always returns True instead of verifying input.",
            ),
            AdversarialFinding(
                severity="WARN",
                category="boundary",
                summary="Missing empty list handling",
                details="Will raise IndexError if passed empty sequence.",
            ),
        ],
    )
    locker.save_run(manifest, patch_content="diff --git a/foo.py b/foo.py\n")

    res = main(["describe", "run-adv-test", "--storage-dir", str(storage)])
    assert res == 0
    out = capsys.readouterr().out
    assert "--- ADVERSARIAL AUDIT ---" in out
    assert "[WARN]" in out or "[CRITICAL]" in out
    assert "Found critical cheating pattern." in out
    assert "[CRITICAL] (anti-cheating) Hardcoded return value" in out
    assert "Function always returns True instead of verifying input." in out
    assert "[WARN] (boundary) Missing empty list handling" in out


def test_cli_describe_renders_adversarial_report_clean(tmp_path: Path, capsys):
    from dark_factory.domain.types import AdversarialReport, EvidenceManifest, RunStatus
    from dark_factory.storage import EvidenceLocker

    storage = tmp_path / ".factory"
    locker = EvidenceLocker(storage_dir=storage)
    manifest = EvidenceManifest.create(run_id="run-clean-test", repo_path="/tmp/repo", base_rev="abc1234")
    manifest.status = RunStatus.AWAITING_REVIEW
    manifest.adversarial_report = AdversarialReport(
        passed=True,
        summary="Clean patch with no red-team findings.",
        findings=[],
    )
    locker.save_run(manifest, patch_content="diff --git a/foo.py b/foo.py\n")

    res = main(["describe", "run-clean-test", "--storage-dir", str(storage)])
    assert res == 0
    out = capsys.readouterr().out
    assert "--- ADVERSARIAL AUDIT ---" in out
    assert "[PASS]" in out
    assert "Clean patch with no red-team findings." in out
    assert "Findings: None" in out


def test_cli_review_displays_adversarial_report_before_action(tmp_path: Path, capsys):
    from dark_factory.domain.types import AdversarialFinding, AdversarialReport, EvidenceManifest, RunStatus
    from dark_factory.orchestrator import DurableEngine

    storage = tmp_path / ".factory"
    engine = DurableEngine(storage_dir=storage)
    manifest = EvidenceManifest.create(run_id="run-review-adv", repo_path="/tmp/repo", base_rev="abc1234")
    manifest.status = RunStatus.AWAITING_REVIEW
    manifest.adversarial_report = AdversarialReport(
        passed=False,
        summary="Suspicious test modification detected.",
        findings=[
            AdversarialFinding(
                severity="WARN",
                category="anti-cheating",
                summary="Relaxed assertion tolerance",
                details="Tolerance changed from 0.001 to 0.1",
            )
        ],
    )
    engine.locker.save_run(manifest, patch_content="diff --git a/foo.py b/foo.py\n")
    with engine._get_connection() as conn:
        conn.execute(
            "INSERT INTO runs (run_id, repo_path, base_rev, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                manifest.run_id,
                manifest.repo_path,
                manifest.base_rev,
                manifest.status.value,
                manifest.created_at,
                manifest.created_at,
            ),
        )

    res = main(["review", "run-review-adv", "--reject", "--storage-dir", str(storage)])
    assert res == 0
    out = capsys.readouterr().out
    assert "ADVERSARIAL AUDIT" in out
    assert "Suspicious test modification detected." in out
    assert "[WARN] (anti-cheating) Relaxed assertion tolerance" in out
    assert "REJECTED" in out


def test_cli_review_interactive_prompt_approve(tmp_path: Path, monkeypatch, capsys):
    import sys

    from dark_factory.domain.types import AdversarialReport, EvidenceManifest, RunStatus
    from dark_factory.orchestrator import DurableEngine

    storage = tmp_path / ".factory"
    engine = DurableEngine(storage_dir=storage)
    manifest = EvidenceManifest.create(run_id="run-interactive-test", repo_path="/tmp/repo", base_rev="abc1234")
    manifest.status = RunStatus.AWAITING_REVIEW
    manifest.adversarial_report = AdversarialReport(
        passed=True,
        summary="Clean patch.",
        findings=[],
    )
    engine.locker.save_run(manifest, patch_content="diff --git a/foo.py b/foo.py\n")
    with engine._get_connection() as conn:
        conn.execute(
            "INSERT INTO runs (run_id, repo_path, base_rev, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                manifest.run_id,
                manifest.repo_path,
                manifest.base_rev,
                manifest.status.value,
                manifest.created_at,
                manifest.created_at,
            ),
        )

    # Mock isatty to True and mock input to return 'y'
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    # Mock activity_apply_patch to avoid real git repo requirement
    import dark_factory.orchestrator.engine as eng_mod

    monkeypatch.setattr(eng_mod, "activity_apply_patch", lambda **kwargs: "commit-rev-123")

    res = main(["review", "run-interactive-test", "--storage-dir", str(storage)])
    assert res == 0
    out = capsys.readouterr().out
    assert "ADVERSARIAL AUDIT" in out
    assert "APPROVED" in out


def test_cli_run_passes_planner_flags(tmp_path: Path, monkeypatch):
    from dark_factory.domain.types import EvidenceManifest, RunStatus
    from dark_factory.orchestrator import DurableEngine

    captured_specs = []

    def mock_execute_run(self, spec, harness=None, run_id=None, status_callback=None):
        captured_specs.append(spec)
        manifest = EvidenceManifest.create(run_id="run-test", repo_path=spec.repo_path, base_rev=spec.base_rev)
        manifest.status = RunStatus.AWAITING_REVIEW
        return manifest

    monkeypatch.setattr(DurableEngine, "execute_run", mock_execute_run)

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "test.sh").write_text("#!/bin/sh\nexit 0\n")

    res = main(
        [
            "run",
            "--repo",
            str(repo),
            "--task",
            "Foo",
            "--planner-model",
            "deepseek-r1:14b",
            "--no-plan",
        ]
    )
    assert res == 0
    assert len(captured_specs) == 1
    assert captured_specs[0].planner_model == "deepseek-r1:14b"
    assert captured_specs[0].skip_plan is True


def test_cli_describe_renders_execution_plan(tmp_path: Path, capsys):
    from dark_factory.domain.types import EvidenceManifest, ExecutionPlan, RunStatus
    from dark_factory.storage import EvidenceLocker

    storage = tmp_path / ".factory"
    locker = EvidenceLocker(storage_dir=storage)
    manifest = EvidenceManifest.create(run_id="run-plan-desc", repo_path="/tmp/repo", base_rev="abc1234")
    manifest.status = RunStatus.AWAITING_REVIEW
    manifest.execution_plan = ExecutionPlan(
        plan_id="plan-1234",
        summary="Introduce modular caching layer",
        invariants=["TTL expiry must be deterministic", "LRU cache size capped at 1000 items"],
        steps=["1. Implement MemoryCache", "2. Connect cache decorator to repo"],
        target_files=["cache.py", "repository.py"],
    )
    locker.save_run(manifest, patch_content="diff --git a/foo.py b/foo.py\n")

    res = main(["describe", "run-plan-desc", "--storage-dir", str(storage)])
    assert res == 0
    out = capsys.readouterr().out
    assert "--- EXECUTION PLAN ---" in out
    assert "Introduce modular caching layer" in out
    assert "TTL expiry must be deterministic" in out
    assert "1. Implement MemoryCache" in out
    assert "cache.py, repository.py" in out


def test_cli_run_passes_mutate_adversarial_flag(tmp_path: Path, monkeypatch):
    captured_specs = []

    class DummyEngine:
        def __init__(self, *args, **kwargs):
            pass

        def execute_run(self, spec, *args, **kwargs):
            captured_specs.append(spec)
            from dark_factory.domain.types import EvidenceManifest, RunStatus

            return EvidenceManifest.create(
                run_id="run-dummy",
                repo_path=spec.repo_path,
                base_rev="abc",
                status=RunStatus.AWAITING_REVIEW,
            )

    monkeypatch.setattr(cli_module, "DurableEngine", DummyEngine)
    monkeypatch.setattr(cli_module, "LocalCoderHarness", lambda **kwargs: None)

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "test.sh").write_text("#!/bin/sh\nexit 0\n")

    res = main(
        [
            "run",
            "--repo",
            str(repo),
            "--task",
            "dummy task",
            "--mutate-adversarial",
        ]
    )
    assert res == 0
    assert len(captured_specs) == 1
    assert captured_specs[0].mutate_adversarial is True


def test_cli_describe_renders_adversarial_mutation(tmp_path: Path, capsys):
    from dark_factory.domain.types import EvidenceManifest, RunStatus
    from dark_factory.storage import EvidenceLocker

    storage = tmp_path / ".factory"
    locker = EvidenceLocker(storage_dir=storage)
    manifest = EvidenceManifest.create(run_id="run-mut-desc", repo_path="/tmp/repo", base_rev="abc1234")
    manifest.status = RunStatus.AWAITING_REVIEW
    manifest.adversarial_test_code = "def test_probe(): assert True\n"
    locker.save_run(manifest, patch_content="diff --git a/foo.py b/foo.py\n")

    res = main(["describe", "run-mut-desc", "--storage-dir", str(storage)])
    assert res == 0
    out = capsys.readouterr().out
    assert "--- ADVERSARIAL MUTATION ---" in out
    assert "def test_probe(): assert True" in out
