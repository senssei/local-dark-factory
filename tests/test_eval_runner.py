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


def test_run_scenario_puts_the_evaluated_model_into_every_task_spec(tmp_path: Path, monkeypatch):
    from dark_factory.orchestrator.engine import DurableEngine

    specs = []
    original = DurableEngine.execute_run

    def record(self, spec, harness=None, run_id=None, **kwargs):
        specs.append(spec)
        return original(self, spec=spec, harness=harness, run_id=run_id, **kwargs)

    monkeypatch.setattr(DurableEngine, "execute_run", record)

    run_scenario(
        SCENARIOS["primes"],
        harness_factory=AlwaysFixPrimesHarness,
        storage_dir=tmp_path / ".factory",
        repeat=2,
        model="Phi-4-mini-instruct-cuda-gpu",
    )

    assert [s.model for s in specs] == ["Phi-4-mini-instruct-cuda-gpu"] * 2
    assert [s.planner_model for s in specs] == [None, None]


def test_run_eval_forwards_its_model_to_the_scenarios(tmp_path: Path, monkeypatch):
    seen = []
    monkeypatch.setattr(
        "dark_factory.eval.runner.run_scenario",
        lambda scenario, **kwargs: seen.append(kwargs.get("model")) or [],
    )

    run_eval(
        ["primes"],
        harness_factory=AlwaysFixPrimesHarness,
        model="Phi-4-mini-instruct-cuda-gpu",
        ollama_url="http://127.0.0.1:1",
        prism_url="http://127.0.0.1:2/v1",
        storage_dir=tmp_path / ".factory",
    )

    assert seen == ["Phi-4-mini-instruct-cuda-gpu"]


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


@pytest.mark.local_engine
def test_eval_real_prism_model_leaves_no_stray_model_loaded(tmp_path: Path):
    """Live residency check for DF-LIVE-01: evaluating a native Prism model with Ollama unreachable must not load
    anything into Ollama, and Prism may hold only the evaluated model. Asserts nothing about convergence. Releases the
    Prism model afterwards through `POST /unload`; never stops the service. Run by hand with `pytest -m local_engine`."""
    import requests
    from engine_fakes import loaded_models

    prism_url = "http://127.0.0.1:5272/v1"
    ollama_url = "http://localhost:11434"
    model = "Phi-4-mini-instruct-cuda-gpu"
    if not LocalCoderHarness(prism_url=prism_url).check_health()["prism"]:
        pytest.skip("Prism is not reachable on localhost.")

    before = loaded_models(ollama_url, prism_url)
    try:
        run_eval(
            ["primes"],
            harness_factory=lambda: LocalCoderHarness(
                model=model, ollama_url="http://127.0.0.1:1", prism_url=prism_url
            ),
            model=model,
            ollama_url="http://127.0.0.1:1",
            prism_url=prism_url,
            storage_dir=tmp_path / ".factory",
            repeat=1,
        )
        after = loaded_models(ollama_url, prism_url)
    finally:
        try:
            requests.post(f"{prism_url}/unload", json={}, timeout=60)
        except requests.RequestException:
            pass

    assert after["ollama"] <= before["ollama"]  # keep-alive may expire a model; nothing new may appear
    assert after["prism"] <= {model}


class RaisingHarness(AgentHarness):
    """Stand-in harness that raises an exception during execute_task."""

    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def execute_task(self, sandbox: Sandbox, task_prompt: str, target_files=None):
        raise self.exc


def test_df_live_05_backend_offline_error_is_recorded_in_eval_result_and_report(tmp_path: Path):
    from dark_factory.domain.errors import LocalEngineOfflineError

    storage_dir = tmp_path / ".factory"
    report = run_eval(
        ["primes"],
        harness_factory=lambda: RaisingHarness(LocalEngineOfflineError("Prism 503 insufficient_resources")),
        model="Phi-4-mini-instruct-cuda-gpu",
        ollama_url="http://127.0.0.1:1",
        prism_url="http://127.0.0.1:5272/v1",
        storage_dir=storage_dir,
        repeat=1,
    )
    assert len(report.results) == 1
    result = report.results[0]
    assert not result.converged
    assert result.status == "FAILED"
    assert getattr(result, "error", None) is not None
    assert "Prism 503" in result.error


def test_df_live_05_transient_backend_error_allows_subsequent_attempts(tmp_path: Path):
    from dark_factory.domain.errors import LocalEngineOfflineError

    call_count = 0

    def harness_factory():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return RaisingHarness(LocalEngineOfflineError("Transient 503"))
        return AlwaysFixPrimesHarness()

    results = run_scenario(
        SCENARIOS["primes"],
        harness_factory=harness_factory,
        storage_dir=tmp_path / ".factory",
        repeat=2,
    )
    assert len(results) == 2
    assert not results[0].converged
    assert results[0].status == "FAILED"
    assert getattr(results[0], "error", None) is not None
    assert "Transient 503" in results[0].error
    assert results[1].converged
    assert results[1].status == "AWAITING_REVIEW"


def test_df_live_05_consecutive_backend_errors_halt_campaign_bounded(tmp_path: Path):
    from dark_factory.domain.errors import LocalEngineOfflineError

    results = run_scenario(
        SCENARIOS["primes"],
        harness_factory=lambda: RaisingHarness(LocalEngineOfflineError("Prism persistent 503")),
        storage_dir=tmp_path / ".factory",
        repeat=5,
    )
    # Bounded to 3 consecutive errors
    assert len(results) == 3
    assert all(not r.converged for r in results)
    assert all(r.status == "FAILED" for r in results)
    assert all(getattr(r, "error", None) and "Prism persistent 503" in r.error for r in results)


def test_df_live_05_keyboard_interrupt_propagates_without_swallowing(tmp_path: Path):
    with pytest.raises(KeyboardInterrupt):
        run_scenario(
            SCENARIOS["primes"],
            harness_factory=lambda: RaisingHarness(KeyboardInterrupt()),
            storage_dir=tmp_path / ".factory",
            repeat=1,
        )


def test_df_live_05_run_eval_keyboard_interrupt_saves_partial_report(tmp_path: Path):
    storage_dir = tmp_path / ".factory"
    call_count = 0

    def harness_factory():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return AlwaysFixPrimesHarness()
        return RaisingHarness(KeyboardInterrupt())

    with pytest.raises(KeyboardInterrupt):
        run_eval(
            ["primes"],
            harness_factory=harness_factory,
            model="Phi-4-mini-instruct-cuda-gpu",
            ollama_url="http://127.0.0.1:1",
            prism_url="http://127.0.0.1:5272/v1",
            storage_dir=storage_dir,
            repeat=2,
        )

    reports = list_eval_reports(storage_dir)
    assert len(reports) == 1
    rep = load_report(reports[0])
    assert len(rep.results) == 1
    assert rep.results[0].converged


def test_df_live_05_consecutive_backend_errors_across_scenarios_halts_campaign(tmp_path: Path):
    from dark_factory.domain.errors import LocalEngineOfflineError

    storage_dir = tmp_path / ".factory"
    report = run_eval(
        ["primes", "calculator"],
        harness_factory=lambda: RaisingHarness(LocalEngineOfflineError("Offline")),
        model="m",
        ollama_url="http://127.0.0.1:1",
        prism_url="http://127.0.0.1:2/v1",
        storage_dir=storage_dir,
        repeat=2,
    )
    # 2 attempts of primes + 1 attempt of calculator = 3 consecutive errors -> halts!
    assert len(report.results) == 3


def test_df_live_06_run_scenario_propagates_target_files_and_protected_paths(tmp_path: Path, monkeypatch):
    from dark_factory.orchestrator.engine import DurableEngine

    specs = []
    original = DurableEngine.execute_run

    def record(self, spec, harness=None, run_id=None, **kwargs):
        specs.append(spec)
        return original(self, spec=spec, harness=harness, run_id=run_id, **kwargs)

    monkeypatch.setattr(DurableEngine, "execute_run", record)

    run_scenario(
        SCENARIOS["primes"],
        harness_factory=AlwaysFixPrimesHarness,
        storage_dir=tmp_path / ".factory",
        repeat=1,
    )

    assert len(specs) == 1
    assert specs[0].target_files == ["primes.py"]
    assert specs[0].protected_paths == ["test_primes.py"]


def test_df_live_06_out_of_scope_patch_fails_eval_run(tmp_path: Path):
    class ExtraneousFileHarness(AgentHarness):
        def execute_task(self, sandbox, task_prompt, target_files=None):
            sandbox.write_file("primes.py", _FIXED_PRIMES.encode("utf-8"))
            sandbox.write_file("stray_helper.py", b"def helper(): pass\n")
            return HarnessResult(success=True, modified_files=["primes.py", "stray_helper.py"])

    results = run_scenario(
        SCENARIOS["primes"],
        harness_factory=ExtraneousFileHarness,
        storage_dir=tmp_path / ".factory",
        repeat=1,
    )
    assert len(results) == 1
    assert results[0].converged is False
    assert results[0].status == "FAILED"
    assert (
        "out_of_scope" in (results[0].operator_notes or "").lower()
        or "out-of-scope" in (results[0].operator_notes or "").lower()
    )
