"""Unit tests for dark_factory.eval.scenarios."""

import subprocess
from pathlib import Path

import pytest

from dark_factory.eval.scenarios import SCENARIOS, EvalScenario


def _git_log_subject(repo: Path) -> str:
    return subprocess.run(
        ["git", "log", "-1", "--format=%s"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_scenario_builds_a_valid_git_repo(name: str, tmp_path: Path):
    scenario = SCENARIOS[name]
    repo = tmp_path / name
    scenario.build_repo(repo)

    assert (repo / ".git").is_dir()
    assert _git_log_subject(repo)  # a commit exists
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout
    assert status.strip() == ""  # nothing left uncommitted


def test_primes_scenario_baseline_fails(tmp_path: Path):
    repo = tmp_path / "primes"
    SCENARIOS["primes"].build_repo(repo)
    result = subprocess.run(["python3", "-m", "pytest", "test_primes.py"], cwd=repo, capture_output=True, text=True)
    assert result.returncode != 0


def test_calculator_scenario_baseline_fails(tmp_path: Path):
    repo = tmp_path / "calculator"
    SCENARIOS["calculator"].build_repo(repo)
    result = subprocess.run(["python3", "-m", "pytest", "test_calculator.py"], cwd=repo, capture_output=True, text=True)
    assert result.returncode != 0


def test_textutils_scenario_baseline_fails(tmp_path: Path):
    repo = tmp_path / "textutils"
    SCENARIOS["textutils"].build_repo(repo)
    result = subprocess.run(["python3", "-m", "pytest", "test_text_utils.py"], cwd=repo, capture_output=True, text=True)
    assert result.returncode != 0


def test_csvparse_scenario_baseline_fails(tmp_path: Path):
    repo = tmp_path / "csvparse"
    SCENARIOS["csvparse"].build_repo(repo)
    result = subprocess.run(["python3", "-m", "pytest", "test_csvparse.py"], cwd=repo, capture_output=True, text=True)
    assert result.returncode != 0


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_scenario_registry_entries_are_well_formed(name: str):
    scenario = SCENARIOS[name]
    assert isinstance(scenario, EvalScenario)
    assert scenario.name == name
    assert scenario.description.strip()
    assert scenario.task_prompt.strip()
    steps = scenario.verification_steps()
    assert steps, f"scenario {name!r} must have at least one verification step"
    for step in steps:
        assert step.argv, f"scenario {name!r} has a verification step with empty argv"
    assert scenario.max_healing_attempts > 0
    assert scenario.timeout_minutes > 0


def test_df_live_06_scenarios_declare_target_files_and_protected_paths(tmp_path: Path):
    for name, scenario in SCENARIOS.items():
        assert hasattr(scenario, "target_files"), f"{name} scenario must have target_files attribute"
        assert scenario.target_files, f"{name} scenario must declare non-empty target_files"
        assert scenario.protected_paths, f"{name} scenario must declare non-empty protected_paths"

        repo = tmp_path / name
        scenario.build_repo(repo)
        for tf in scenario.target_files:
            assert (repo / tf).exists(), f"{name} target_file {tf} does not exist in scaffolded repo"
        for pp in scenario.protected_paths:
            assert (repo / pp).exists(), f"{name} protected_path {pp} does not exist in scaffolded repo"


def test_df_live_06_primes_edge_cases_in_test_suite(tmp_path: Path):
    repo = tmp_path / "primes"
    SCENARIOS["primes"].build_repo(repo)
    test_content = (repo / "test_primes.py").read_text(encoding="utf-8")
    assert "is_prime(0)" in test_content
    assert "is_prime(1)" in test_content
    assert "is_prime(-1)" in test_content
    assert "is_prime(9)" in test_content


def test_df_live_06_calculator_edge_cases_in_test_suite(tmp_path: Path):
    repo = tmp_path / "calculator"
    SCENARIOS["calculator"].build_repo(repo)
    test_content = (repo / "test_calculator.py").read_text(encoding="utf-8")
    assert "0" in test_content
    assert "ValueError" in test_content


def test_df_live_06_textutils_edge_cases_in_test_suite(tmp_path: Path):
    repo = tmp_path / "textutils"
    SCENARIOS["textutils"].build_repo(repo)
    test_content = (repo / "test_text_utils.py").read_text(encoding="utf-8")
    assert "\\t" in test_content or "\t" in test_content or "tab" in test_content.lower()


def test_df_live_06_csvparse_edge_cases_in_test_suite(tmp_path: Path):
    repo = tmp_path / "csvparse"
    SCENARIOS["csvparse"].build_repo(repo)
    test_content = (repo / "test_csvparse.py").read_text(encoding="utf-8")
    assert "empty" in test_content.lower() or ",''," in test_content or ',"",' in test_content or ",," in test_content
