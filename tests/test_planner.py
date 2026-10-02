"""Unit tests for LocalPlanner in dark_factory.planning."""

from unittest.mock import MagicMock

from dark_factory.domain.types import ModelTelemetry
from dark_factory.planning.planner import LocalPlanner


def test_planner_parses_clean_json():
    mock_harness = MagicMock()
    json_response = """{
        "summary": "Implement prime sieve",
        "invariants": ["n <= 1 returns False", "Time complexity O(sqrt(n))"],
        "steps": ["1. Check base cases", "2. Loop up to sqrt(n)"],
        "target_files": ["primes.py"]
    }"""
    mock_harness._call_model.return_value = (json_response, ModelTelemetry("ollama", "deepseek-r1:14b"))

    planner = LocalPlanner(harness=mock_harness)
    plan = planner.generate_plan(task_prompt="Fix is_prime", context="Existing primes.py", plan_id="plan-clean-01")

    assert plan.plan_id == "plan-clean-01"
    assert plan.summary == "Implement prime sieve"
    assert len(plan.invariants) == 2
    assert "n <= 1 returns False" in plan.invariants
    assert len(plan.steps) == 2
    assert plan.target_files == ["primes.py"]
    assert plan.raw_plan == json_response


def test_planner_extracts_json_from_code_fence():
    mock_harness = MagicMock()
    fenced_response = """Here is the execution plan:
```json
{
    "summary": "Add CSV quoting support",
    "invariants": ["Escaped quotes must be unescaped"],
    "steps": ["1. Update parse_row logic"],
    "target_files": ["csv_parser.py"]
}
```
Good luck!"""
    mock_harness._call_model.return_value = (fenced_response, ModelTelemetry("ollama", "deepseek-r1:14b"))

    planner = LocalPlanner(harness=mock_harness)
    plan = planner.generate_plan(task_prompt="Support quoted CSV")

    assert plan.summary == "Add CSV quoting support"
    assert plan.target_files == ["csv_parser.py"]
    assert "Escaped quotes must be unescaped" in plan.invariants


def test_planner_fallback_on_malformed_json():
    mock_harness = MagicMock()
    raw_prose = "I suggest we create a new file named utils.py and put the helper function there."
    mock_harness._call_model.return_value = (raw_prose, ModelTelemetry("ollama", "deepseek-r1:14b"))

    planner = LocalPlanner(harness=mock_harness)
    plan = planner.generate_plan(task_prompt="Add utils helper")

    assert plan.plan_id.startswith("plan-")
    assert plan.summary == "Autonomous execution plan"
    assert plan.raw_plan == raw_prose
    assert len(plan.steps) >= 1


def test_planner_handles_harness_exception():
    mock_harness = MagicMock()
    mock_harness._call_model.side_effect = RuntimeError("Inference engine connection refused")

    planner = LocalPlanner(harness=mock_harness)
    plan = planner.generate_plan(task_prompt="Do something")

    assert "Inference engine connection refused" in plan.summary
    assert plan.raw_plan != ""
