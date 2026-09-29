"""Repeatable real-model evaluation harness for Sovereign Dark Factory."""

from dark_factory.eval.runner import EvalReport, EvalRunResult, run_eval
from dark_factory.eval.scenarios import SCENARIOS, EvalScenario

__all__ = ["SCENARIOS", "EvalReport", "EvalRunResult", "EvalScenario", "run_eval"]
