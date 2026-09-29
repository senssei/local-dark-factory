"""Unit tests for dark_factory.eval.runner — deterministic stub harnesses only, no real model."""

from pathlib import Path

import pytest

from dark_factory.eval.runner import (
    EvalReport,
    EvalRunResult,
    format_summary,
    list_eval_reports,
    load_report,
    run_eval,
    run_scenario,
    save_report,
)
from dark_factory.eval.scenarios import SCENARIOS
from dark_factory.harness.base import AgentHarness, HarnessResult
from dark_factory.harness.local_coder import LocalCoderHarness
from dark_factory.sandbox.base import Sandbox

_FIXED_PRIMES = (
    "def is_prime(n: int) -> bool:\n"
    "    if n < 2:\n"
    "        return False\n"
    "    for i in range(2, int(n**0.5) + 1):\n"
    "        if n % i == 0:\n"
    "            return False\n"
    "    return True\n"
)


class AlwaysFixPrimesHarness(AgentHarness):
    """Deterministic stand-in for a real model that always solves the `primes` scenario first try."""

    def execute_task(self, sandbox: Sandbox, task_prompt: str, target_files=None):
        sandbox.write_file("primes.py", _FIXED_PRIMES.encode("utf-8"))
        return HarnessResult(success=True, modified_files=["primes.py"])


class NeverFixHarness(AgentHarness):
    """Deterministic stand-in for a model that never solves the task (writes back the same broken code)."""

    def __init__(self, broken_content: bytes, target_file: str) -> None:
        self.broken_content = broken_content
        self.target_file = target_file

    def execute_task(self, sandbox: Sandbox, task_prompt: str, target_files=None):
        sandbox.write_file(self.target_file, self.broken_content)
        return HarnessResult(success=True, modified_files=[self.target_file])


def test_run_scenario_repeat_count_and_convergence(tmp_path: Path):
    results = run_scenario(
        SCENARIOS["primes"],
        harness_factory=AlwaysFixPrimesHarness,
        storage_dir=tmp_path / ".factory",
        repeat=3,
    )
    assert len(results) == 3
    assert all(r.converged for r in results)
    assert all(r.scenario == "primes" for r in results)
    assert all(r.healing_attempts == 0 for r in results)
    assert all(not r.repeated_failure_streak_fired for r in results)
    assert all(isinstance(r, EvalRunResult) for r in results)


def test_run_scenario_never_converges_and_flags_stuck(tmp_path: Path):
    results = run_scenario(
        SCENARIOS["primes"],
        harness_factory=lambda: NeverFixHarness(b"def is_prime(n):\n    return False\n", "primes.py"),
        storage_dir=tmp_path / ".factory",
        repeat=1,
    )
    assert len(results) == 1
    assert not results[0].converged
    assert results[0].repeated_failure_streak_fired


def test_run_scenario_uses_separate_eval_runs_journal_not_main_factory(tmp_path: Path):
    storage_dir = tmp_path / ".factory"
    run_scenario(
        SCENARIOS["primes"],
        harness_factory=AlwaysFixPrimesHarness,
        storage_dir=storage_dir,
        repeat=1,
    )
    assert (storage_dir / "eval-runs" / "factory.db").exists()
    assert not (storage_dir / "runs").exists()  # main journal's evidence dir was never touched


def test_run_scenario_keep_repos_leaves_scaffolded_repo_on_disk(tmp_path: Path):
    storage_dir = tmp_path / ".factory"
    run_scenario(
        SCENARIOS["primes"],
        harness_factory=AlwaysFixPrimesHarness,
        storage_dir=storage_dir,
        repeat=1,
        keep_repos=True,
    )
    kept = storage_dir / "eval-runs" / "scratch" / "primes-1"
    assert (kept / "primes.py").exists()


def test_run_eval_builds_report_with_scenario_summary(tmp_path: Path):
    report = run_eval(
        ["primes"],
        harness_factory=AlwaysFixPrimesHarness,
        model="stub-model",
        ollama_url="http://localhost:11434",
        prism_url="http://127.0.0.1:5272/v1",
        storage_dir=tmp_path / ".factory",
        repeat=2,
    )
    assert isinstance(report, EvalReport)
    assert len(report.results) == 2
    summary = report.scenario_summary()
    assert summary["primes"]["attempts"] == 2
    assert summary["primes"]["converged"] == 2
    assert summary["primes"]["convergence_rate"] == 1.0
    assert summary["primes"]["avg_healing_attempts"] == 0.0
    assert summary["primes"]["any_stuck"] is False
    assert "primes" in format_summary(report)


def test_run_eval_defaults_to_every_registered_scenario_when_none_named(tmp_path: Path):
    report = run_eval(
        None,
        harness_factory=AlwaysFixPrimesHarness,
        model="stub-model",
        ollama_url="http://localhost:11434",
        prism_url="http://127.0.0.1:5272/v1",
        storage_dir=tmp_path / ".factory",
        repeat=1,
    )
    assert {r.scenario for r in report.results} == set(SCENARIOS)


def test_save_and_load_report_round_trip(tmp_path: Path):
    storage_dir = tmp_path / ".factory"
    report = run_eval(
        ["primes"],
        harness_factory=AlwaysFixPrimesHarness,
        model="stub-model",
        ollama_url="http://localhost:11434",
        prism_url="http://127.0.0.1:5272/v1",
        storage_dir=storage_dir,
        repeat=1,
    )
    path = save_report(report, storage_dir)
    assert path.exists()

    loaded = load_report(path)
    assert loaded.model == report.model
    assert len(loaded.results) == len(report.results)
    assert loaded.results[0].scenario == "primes"
    assert loaded.scenario_summary() == report.scenario_summary()


def test_list_eval_reports_sorted_and_empty_when_none_saved(tmp_path: Path):
    storage_dir = tmp_path / ".factory"
    assert list_eval_reports(storage_dir) == []

    report = run_eval(
        ["primes"],
        harness_factory=AlwaysFixPrimesHarness,
        model="stub-model",
        ollama_url="http://localhost:11434",
        prism_url="http://127.0.0.1:5272/v1",
        storage_dir=storage_dir,
        repeat=1,
    )
    first = save_report(report, storage_dir)
    second = save_report(report, storage_dir)

    reports = list_eval_reports(storage_dir)
    assert reports == sorted([first, second])


@pytest.mark.local_engine
def test_run_eval_real_model_smoke(tmp_path: Path):
    """Only proves the pipeline produces a well-formed report against a real engine — never asserts a
    specific convergence rate, which is inherently nondeterministic (same standard as the real-model e2e
    tests in `tests/test_e2e.py`). Run by hand with `pytest -m local_engine`."""
    health = LocalCoderHarness().check_health()
    if not health["ollama"] and not health["prism"]:
        pytest.skip("No local inference engine (Ollama/Prism) reachable on localhost.")

    report = run_eval(
        ["primes"],
        harness_factory=LocalCoderHarness,
        model="qwen2.5-coder:14b",
        ollama_url="http://localhost:11434",
        prism_url="http://127.0.0.1:5272/v1",
        storage_dir=tmp_path / ".factory",
        repeat=1,
    )

    assert len(report.results) == 1
    result = report.results[0]
    assert result.scenario == "primes"
    assert result.status  # some terminal RunStatus value, whatever it turned out to be
    assert result.duration_sec >= 0
