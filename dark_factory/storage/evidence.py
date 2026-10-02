"""Evidence locker and persistent storage for Sovereign Dark Factory."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path

from dark_factory.domain.errors import RunNotFoundError
from dark_factory.domain.types import (
    AdversarialFinding,
    AdversarialReport,
    EvidenceManifest,
    ExecutionPlan,
    ModelTelemetry,
    PhaseTiming,
    RunStatus,
    StepExecution,
)
from dark_factory.harness.llm_text import clean_text, fence, md_cell


def _finding_from_dict(data: dict) -> AdversarialFinding:
    """Build a finding from stored JSON, ignoring keys written by newer versions."""
    return AdversarialFinding(
        severity=data.get("severity", "WARN"),
        category=data.get("category", "boundary"),
        summary=data.get("summary", ""),
        details=data.get("details", ""),
    )


class EvidenceLocker:
    """Stores and retrieves run manifests, git diffs, and execution evidence."""

    def __init__(self, storage_dir: str | Path = ".factory") -> None:
        self.storage_dir = Path(storage_dir).resolve()
        self.runs_dir = self.storage_dir / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def save_run(
        self,
        manifest: EvidenceManifest,
        patch_content: str = "",
        transcript: str = "",
    ) -> Path:
        """Persist full evidence for a run."""
        run_folder = self.runs_dir / manifest.run_id
        run_folder.mkdir(parents=True, exist_ok=True)

        # Write diff.patch
        patch_file = run_folder / "diff.patch"
        patch_file.write_text(patch_content, encoding="utf-8")
        manifest.patch_path = str(patch_file)
        manifest.patch_size_bytes = len(patch_content.encode("utf-8"))
        manifest.patch_sha256 = (
            hashlib.sha256(patch_content.encode("utf-8")).hexdigest() if patch_content.strip() else None
        )

        # Write transcript.log
        if transcript:
            (run_folder / "transcript.log").write_text(transcript, encoding="utf-8")

        # Write telemetry.json
        if manifest.model_telemetry:
            telem_file = run_folder / "telemetry.json"
            telem_file.write_text(json.dumps(asdict(manifest.model_telemetry), indent=2), encoding="utf-8")

        # Write adversarial.md
        if manifest.adversarial_report:
            adv_file = run_folder / "adversarial.md"
            status_badge = "PASSED" if manifest.adversarial_report.passed else "WARNINGS DETECTED"
            lines = [
                "# Adversarial Red-Team Report",
                "",
                f"**Status:** {status_badge}",
                f"**Summary:** {md_cell(manifest.adversarial_report.summary)}",
                "",
            ]
            if manifest.adversarial_report.findings:
                lines.extend(
                    [
                        "## Findings",
                        "",
                        "| Severity | Category | Summary | Details |",
                        "|---|---|---|---|",
                    ]
                )
                for f in manifest.adversarial_report.findings:
                    lines.append(
                        f"| {f.severity} | {md_cell(f.category)} | {md_cell(f.summary)} | {md_cell(f.details)} |"
                    )
            adv_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # Write plan.md if execution plan is present
        if manifest.execution_plan:
            plan_file = run_folder / "plan.md"
            plan = manifest.execution_plan
            lines = [
                f"# Execution Plan: {plan.plan_id}",
                "",
                f"**Summary:** {md_cell(plan.summary)}",
                "",
            ]
            if plan.invariants:
                lines.extend(["## Architectural Invariants", ""])
                for inv in plan.invariants:
                    lines.append(f"- {md_cell(inv)}")
                lines.append("")
            if plan.steps:
                lines.extend(["## Implementation Steps", ""])
                for step in plan.steps:
                    lines.append(f"- {md_cell(step)}")
                lines.append("")
            if plan.target_files:
                lines.extend(["## Target Files", ""])
                for tf in plan.target_files:
                    lines.append(f"- `{md_cell(tf).replace(chr(96), chr(39))}`")
                lines.append("")
            if plan.raw_plan:
                lines.extend(["## Raw Reasoning", "", fence(clean_text(plan.raw_plan)), ""])
            plan_file.write_text("\n".join(lines), encoding="utf-8")

        # Write adversarial_test.py if adversarial test code is present
        if manifest.adversarial_test_code:
            adv_test_file = run_folder / "adversarial_test.py"
            adv_test_file.write_text(manifest.adversarial_test_code, encoding="utf-8")

        # Write manifest.json
        manifest_file = run_folder / "manifest.json"
        manifest_data = asdict(manifest)
        # Written last and atomically: a readable manifest.json proves the rest of the evidence is complete.
        tmp_file = manifest_file.with_suffix(".json.tmp")
        tmp_file.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
        os.replace(tmp_file, manifest_file)

        return run_folder

    def load_manifest(self, run_id: str) -> EvidenceManifest:
        """Load manifest by run ID."""
        manifest_file = self.runs_dir / run_id / "manifest.json"
        if not manifest_file.exists():
            raise RunNotFoundError(f"Run ID '{run_id}' not found in evidence locker.")

        data = json.loads(manifest_file.read_text(encoding="utf-8"))

        # Reconstruct domain objects
        status = RunStatus(data["status"])
        telemetry = None
        if data.get("model_telemetry"):
            telemetry = ModelTelemetry(**data["model_telemetry"])

        verification_results = [StepExecution(**step) for step in data.get("verification_results", [])]
        phase_timings = [PhaseTiming(**pt) for pt in data.get("phase_timings", [])]

        adv_report = None
        if data.get("adversarial_report"):
            ar_data = data["adversarial_report"]
            findings = [_finding_from_dict(f) for f in ar_data.get("findings", [])]
            adv_report = AdversarialReport(
                passed=ar_data.get("passed", False),
                summary=ar_data.get("summary", ""),
                findings=findings,
            )

        execution_plan = None
        if data.get("execution_plan"):
            ep_data = data["execution_plan"]
            execution_plan = ExecutionPlan(
                plan_id=ep_data.get("plan_id", ""),
                summary=ep_data.get("summary", ""),
                invariants=ep_data.get("invariants", []),
                steps=ep_data.get("steps", []),
                target_files=ep_data.get("target_files", []),
                raw_plan=ep_data.get("raw_plan", ""),
            )

        return EvidenceManifest(
            run_id=data["run_id"],
            status=status,
            repo_path=data["repo_path"],
            base_rev=data["base_rev"],
            created_at=data["created_at"],
            completed_at=data.get("completed_at"),
            resulting_rev=data.get("resulting_rev"),
            patch_path=data.get("patch_path"),
            patch_size_bytes=data.get("patch_size_bytes", 0),
            patch_sha256=data.get("patch_sha256"),
            healing_attempts=data.get("healing_attempts", 0),
            verification_results=verification_results,
            model_telemetry=telemetry,
            operator_notes=data.get("operator_notes"),
            phase_timings=phase_timings,
            repeated_failure_streak=data.get("repeated_failure_streak", 0),
            adversarial_report=adv_report,
            execution_plan=execution_plan,
            adversarial_test_code=data.get("adversarial_test_code"),
        )

    def load_patch(self, run_id: str) -> str:
        """Load patch diff for a run."""
        patch_file = self.runs_dir / run_id / "diff.patch"
        if not patch_file.exists():
            return ""
        return patch_file.read_text(encoding="utf-8")

    def list_runs(self) -> list[EvidenceManifest]:
        """List all preserved runs ordered by creation time descending."""
        runs = []
        if not self.runs_dir.exists():
            return runs

        for run_folder in self.runs_dir.iterdir():
            if run_folder.is_dir() and (run_folder / "manifest.json").exists():
                try:
                    runs.append(self.load_manifest(run_folder.name))
                except Exception:
                    continue

        runs.sort(key=lambda m: m.created_at, reverse=True)
        return runs
