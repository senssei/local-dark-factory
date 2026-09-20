"""Evidence locker and persistent storage for Sovereign Dark Factory."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from dark_factory.domain.errors import RunNotFoundError
from dark_factory.domain.types import (
    EvidenceManifest,
    ModelTelemetry,
    RunStatus,
    StepExecution,
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

        # Write manifest.json
        manifest_file = run_folder / "manifest.json"
        manifest_data = asdict(manifest)
        manifest_file.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

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
