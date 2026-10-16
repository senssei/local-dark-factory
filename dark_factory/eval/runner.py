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
    error: str | None = None


MAX_CONSECUTIVE_BACKEND_ERRORS: int = 3


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
            errors = [r for r in attempts if r.error is not None]
            summary[scenario_name] = {
                "attempts": len(attempts),
                "converged": len(converged),
                "errors": len(errors),
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
    model: str | None = None,
    results: list[EvalRunResult] | None = None,
    consecutive_backend_errors: int = 0,
) -> list[EvalRunResult]:
    """Run one scenario `repeat` times, each against a fresh scaffolded repo."""
    engine = DurableEngine(storage_dir=storage_dir / "eval-runs")
    scenario_results: list[EvalRunResult] = []

    for attempt in range(1, repeat + 1):
        if consecutive_backend_errors >= MAX_CONSECUTIVE_BACKEND_ERRORS:
            if status_callback:
                status_callback(
                    f"[{scenario.name}] halted after {consecutive_backend_errors} consecutive backend errors"
                )
            break

        if keep_repos:
            repo_path = storage_dir / "eval-runs" / "scratch" / f"{scenario.name}-{attempt}"
            repo_path.mkdir(parents=True, exist_ok=True)
            scratch_root: Path | None = None
        else:
            scratch_root = Path(tempfile.mkdtemp(prefix=f"dark-factory-eval-{scenario.name}-"))
            repo_path = scratch_root / scenario.name

        try:
            scenario.build_repo(repo_path)

            model_args = {"model": model} if model else {}
            spec = TaskSpec(
                **model_args,
                repo_path=str(repo_path),
                task_prompt=scenario.task_prompt,
                verification_steps=scenario.verification_steps(),
                protected_paths=list(scenario.protected_paths),
                target_files=list(scenario.target_files),
                max_healing_attempts=scenario.max_healing_attempts,
                timeout_minutes=scenario.timeout_minutes,
            )

            run_id = f"eval-{scenario.name}-{attempt}-{int(time.time() * 1000)}"
            if status_callback:
                status_callback(f"[{scenario.name} {attempt}/{repeat}] running...")

            start = time.monotonic()
            try:
                manifest = engine.execute_run(spec=spec, harness=harness_factory(), run_id=run_id)
                duration = time.monotonic() - start
                consecutive_backend_errors = 0

                telemetry = manifest.model_telemetry
                res = EvalRunResult(
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
                scenario_results.append(res)
                if results is not None:
                    results.append(res)
                if status_callback:
                    status_callback(f"[{scenario.name} {attempt}/{repeat}] {manifest.status.value}")
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as exc:
                duration = time.monotonic() - start
                consecutive_backend_errors += 1
                notes = f"Unhandled backend exception: {exc}"
                healing = 0
                streak = False
                status_val = RunStatus.FAILED.value
                try:
                    m = engine.locker.load_manifest(run_id)
                    status_val = m.status.value
                    healing = m.healing_attempts
                    streak = m.repeated_failure_streak >= 1
                    if m.operator_notes:
                        notes = m.operator_notes
                except Exception:
                    pass

                res = EvalRunResult(
                    scenario=scenario.name,
                    run_id=run_id,
                    converged=False,
                    status=status_val,
                    healing_attempts=healing,
                    repeated_failure_streak_fired=streak,
                    duration_sec=round(duration, 3),
                    operator_notes=notes,
                    error=str(exc),
                )
                scenario_results.append(res)
                if results is not None:
                    results.append(res)
                if status_callback:
                    status_callback(f"[{scenario.name} {attempt}/{repeat}] FAILED ({exc})")
        finally:
            if scratch_root is not None:
                shutil.rmtree(scratch_root, ignore_errors=True)

    return scenario_results


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
    consecutive_errors = 0
    try:
        for name in names:
            if consecutive_errors >= MAX_CONSECUTIVE_BACKEND_ERRORS:
                if status_callback:
                    status_callback(f"[{name}] halted after {consecutive_errors} consecutive backend errors")
                break
            scenario = SCENARIOS[name]
            scen_results = run_scenario(
                scenario,
                harness_factory=harness_factory,
                storage_dir=storage_dir,
                repeat=repeat,
                keep_repos=keep_repos,
                status_callback=status_callback,
                model=model,
                results=results,
                consecutive_backend_errors=consecutive_errors,
            )
            if scen_results:
                for r in scen_results:
                    if not any(r is existing for existing in results):
                        results.append(r)

            consecutive_errors = 0
            for r in reversed(results):
                if r.error is not None:
                    consecutive_errors += 1
                else:
                    break
    except (KeyboardInterrupt, SystemExit):
        if results:
            partial_report = EvalReport(
                started_at=started_at,
                finished_at=datetime.now(UTC).isoformat(),
                model=model,
                ollama_url=ollama_url,
                prism_url=prism_url,
                results=results,
            )
            save_report(partial_report, storage_dir)
        raise

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
