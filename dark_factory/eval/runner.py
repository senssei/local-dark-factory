"""Runner for the repeatable real-model evaluation harness.

Drives each `EvalScenario` through a real `DurableEngine`, in a **separate** journal
(`<storage_dir>/eval-runs`) from the operator's main `.factory` run history — eval scenarios are throwaway
scaffold repos, and must never show up in `dark-factory list`/`review` or be approvable by accident.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from dark_factory.domain.types import RunStatus, TaskSpec
from dark_factory.eval.scenarios import SCENARIOS, EvalScenario
from dark_factory.harness.base import AgentHarness
from dark_factory.orchestrator.engine import DurableEngine


@dataclass
class EvalRunResult:
    """Outcome of a single real attempt at one scenario."""

    scenario: str
    run_id: str
    converged: bool
    status: str
    healing_attempts: int
    repeated_failure_streak_fired: bool
    duration_sec: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tokens_per_sec: float = 0.0
    operator_notes: str | None = None


@dataclass
class EvalReport:
    """A full evaluation run: metadata plus one `EvalRunResult` per scenario attempt."""

    started_at: str
    finished_at: str
    model: str
    ollama_url: str
    prism_url: str
    results: list[EvalRunResult] = field(default_factory=list)

    def scenario_summary(self) -> dict[str, dict]:
        """Per-scenario convergence rate and average healing attempts."""
        summary: dict[str, dict] = {}
        for scenario_name in dict.fromkeys(r.scenario for r in self.results):
            attempts = [r for r in self.results if r.scenario == scenario_name]
            converged = [r for r in attempts if r.converged]
            summary[scenario_name] = {
                "attempts": len(attempts),
                "converged": len(converged),
                "convergence_rate": len(converged) / len(attempts) if attempts else 0.0,
                "avg_healing_attempts": (
                    sum(r.healing_attempts for r in attempts) / len(attempts) if attempts else 0.0
                ),
                "any_stuck": any(r.repeated_failure_streak_fired for r in attempts),
            }
        return summary


def run_scenario(
    scenario: EvalScenario,
    *,
    harness_factory: Callable[[], AgentHarness],
    storage_dir: Path,
    repeat: int = 1,
    keep_repos: bool = False,
    status_callback: Callable[[str], None] | None = None,
) -> list[EvalRunResult]:
    """Run one scenario `repeat` times, each against a fresh scaffolded repo."""
    engine = DurableEngine(storage_dir=storage_dir / "eval-runs")
    results: list[EvalRunResult] = []

    for attempt in range(1, repeat + 1):
        if keep_repos:
            repo_path = storage_dir / "eval-runs" / "scratch" / f"{scenario.name}-{attempt}"
            repo_path.mkdir(parents=True, exist_ok=True)
            scratch_root: Path | None = None
        else:
            scratch_root = Path(tempfile.mkdtemp(prefix=f"dark-factory-eval-{scenario.name}-"))
            repo_path = scratch_root / scenario.name

        try:
            scenario.build_repo(repo_path)

            spec = TaskSpec(
                repo_path=str(repo_path),
                task_prompt=scenario.task_prompt,
                verification_steps=scenario.verification_steps(),
                protected_paths=list(scenario.protected_paths),
                max_healing_attempts=scenario.max_healing_attempts,
                timeout_minutes=scenario.timeout_minutes,
            )

            run_id = f"eval-{scenario.name}-{attempt}-{int(time.time() * 1000)}"
            if status_callback:
                status_callback(f"[{scenario.name} {attempt}/{repeat}] running...")

            start = time.monotonic()
            manifest = engine.execute_run(spec=spec, harness=harness_factory(), run_id=run_id)
            duration = time.monotonic() - start

            telemetry = manifest.model_telemetry
            results.append(
                EvalRunResult(
                    scenario=scenario.name,
                    run_id=run_id,
                    converged=manifest.status == RunStatus.AWAITING_REVIEW,
                    status=manifest.status.value,
                    healing_attempts=manifest.healing_attempts,
                    repeated_failure_streak_fired=manifest.repeated_failure_streak >= 1,
                    duration_sec=round(duration, 3),
                    prompt_tokens=telemetry.prompt_tokens if telemetry else 0,
                    completion_tokens=telemetry.completion_tokens if telemetry else 0,
                    tokens_per_sec=telemetry.tokens_per_sec if telemetry else 0.0,
                    operator_notes=manifest.operator_notes,
                )
            )
            if status_callback:
                status_callback(f"[{scenario.name} {attempt}/{repeat}] {manifest.status.value}")
        finally:
            if scratch_root is not None:
                shutil.rmtree(scratch_root, ignore_errors=True)

    return results


def run_eval(
    scenario_names: list[str] | None,
    *,
    harness_factory: Callable[[], AgentHarness],
    model: str,
    ollama_url: str,
    prism_url: str,
    storage_dir: Path,
    repeat: int = 1,
    keep_repos: bool = False,
    status_callback: Callable[[str], None] | None = None,
) -> EvalReport:
    """Run the named scenarios (or every registered scenario) and assemble a report."""
    names = scenario_names or sorted(SCENARIOS)
    started_at = datetime.now(UTC).isoformat()

    results: list[EvalRunResult] = []
    for name in names:
        scenario = SCENARIOS[name]
        results.extend(
            run_scenario(
                scenario,
                harness_factory=harness_factory,
                storage_dir=storage_dir,
                repeat=repeat,
                keep_repos=keep_repos,
                status_callback=status_callback,
            )
        )

    return EvalReport(
        started_at=started_at,
        finished_at=datetime.now(UTC).isoformat(),
        model=model,
        ollama_url=ollama_url,
        prism_url=prism_url,
        results=results,
    )


def _evals_dir(storage_dir: Path) -> Path:
    d = Path(storage_dir) / "evals"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_report(report: EvalReport, storage_dir: Path) -> Path:
    """Persist a report as `<storage_dir>/evals/<timestamp>.json`."""
    filename = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ") + ".json"
    path = _evals_dir(storage_dir) / filename
    path.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    return path


def load_report(path: Path) -> EvalReport:
    """Load a report previously written by `save_report`."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    results = [EvalRunResult(**r) for r in data.get("results", [])]
    return EvalReport(
        started_at=data["started_at"],
        finished_at=data["finished_at"],
        model=data["model"],
        ollama_url=data["ollama_url"],
        prism_url=data["prism_url"],
        results=results,
    )


def list_eval_reports(storage_dir: Path) -> list[Path]:
    """List saved eval report files, oldest first (filenames are timestamp-sortable)."""
    d = Path(storage_dir) / "evals"
    if not d.exists():
        return []
    return sorted(d.glob("*.json"))


def format_summary(report: EvalReport) -> str:
    """Human-readable convergence-rate table for CLI output."""
    lines = [f"Eval report: {report.model} ({report.started_at} -> {report.finished_at})", ""]
    lines.append(f"{'SCENARIO':<15} {'ATTEMPTS':<10} {'CONVERGED':<11} {'RATE':<8} {'AVG HEALING':<12} STUCK?")
    for name, s in report.scenario_summary().items():
        lines.append(
            f"{name:<15} {s['attempts']:<10} {s['converged']:<11} "
            f"{s['convergence_rate']:.0%}{'':<3} {s['avg_healing_attempts']:<12.1f} "
            f"{'yes' if s['any_stuck'] else 'no'}"
        )
    return "\n".join(lines)
