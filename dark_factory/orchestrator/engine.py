"""Durable SQLite workflow engine for Sovereign Dark Factory."""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from dark_factory.domain.errors import WorkflowStateError
from dark_factory.domain.types import EvidenceManifest, RunStatus, TaskSpec
from dark_factory.harness.base import AgentHarness
from dark_factory.harness.local_coder import LocalCoderHarness
from dark_factory.orchestrator.activities import (
    activity_apply_patch,
    activity_cleanup_sandbox,
    activity_create_sandbox,
    activity_execute_task_and_verify,
    activity_preserve_evidence,
)
from dark_factory.storage.evidence import EvidenceLocker


class DurableEngine:
    """Orchestrates durable runs, state transitions, and operator review gates."""

    def __init__(
        self,
        storage_dir: str | Path = ".factory",
        db_name: str = "factory.db",
    ) -> None:
        self.storage_dir = Path(storage_dir).resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.storage_dir / db_name
        self.locker = EvidenceLocker(self.storage_dir)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    repo_path TEXT NOT NULL,
                    base_rev TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    operator_notes TEXT
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(run_id)
                );
                """
            )

    def transition_status(
        self,
        run_id: str,
        new_status: RunStatus,
        payload: dict | None = None,
    ) -> None:
        """Atomically transition run status and record audit event."""
        now = datetime.now(UTC).isoformat()
        payload_json = json.dumps(payload or {})
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE runs
                SET status = ?, updated_at = ?
                WHERE run_id = ?;
                """,
                (new_status.value, now, run_id),
            )
            conn.execute(
                """
                INSERT INTO events (run_id, event_type, payload, created_at)
                VALUES (?, ?, ?, ?);
                """,
                (run_id, new_status.value, payload_json, now),
            )

    def execute_run(
        self,
        spec: TaskSpec,
        harness: AgentHarness | None = None,
        run_id: str | None = None,
        status_callback: Callable[[RunStatus], None] | None = None,
    ) -> EvidenceManifest:
        """Execute a full autonomous dark factory run."""
        if run_id is None:
            now_str = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
            short_id = uuid.uuid4().hex[:6]
            run_id = f"run-{now_str}-{short_id}"

        if harness is None:
            harness = LocalCoderHarness(model=spec.model)

        now = datetime.now(UTC).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO runs (run_id, repo_path, base_rev, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (run_id, str(spec.repo_path), spec.base_rev, RunStatus.PENDING.value, now, now),
            )

        manifest = EvidenceManifest.create(
            run_id=run_id,
            repo_path=str(spec.repo_path),
            base_rev=spec.base_rev,
            status=RunStatus.PENDING,
        )

        def update_state(st: RunStatus, pld=None):
            manifest.status = st
            self.transition_status(run_id, st, pld)
            if status_callback:
                status_callback(st)

        sandbox = None
        try:
            # 1. Create Sandbox
            update_state(RunStatus.CREATING_SANDBOX)
            sandbox = activity_create_sandbox(
                spec=spec,
                run_id=run_id,
                base_dir=self.storage_dir / "sandboxes",
            )

            # 2. Run Agent & Verification Loop
            update_state(RunStatus.AGENT_RUNNING)
            passed, healing_attempts, executions, telemetry = activity_execute_task_and_verify(
                sandbox=sandbox,
                harness=harness,
                spec=spec,
            )

            # 3. Assess Result & Preserve Evidence
            if passed:
                update_state(RunStatus.AWAITING_REVIEW)
            else:
                update_state(RunStatus.FAILED)

            activity_preserve_evidence(
                sandbox=sandbox,
                locker=self.locker,
                manifest=manifest,
                executions=executions,
                healing_attempts=healing_attempts,
                telemetry=telemetry,
            )

            return manifest

        except Exception as e:
            update_state(RunStatus.FAILED, {"error": str(e)})
            manifest.status = RunStatus.FAILED
            manifest.operator_notes = f"Run encountered unhandled error: {e}"
            self.locker.save_run(manifest, transcript=f"ERROR: {e}")
            raise
        finally:
            if sandbox is not None:
                activity_cleanup_sandbox(sandbox)

    def review_run(
        self,
        run_id: str,
        approve: bool,
        target_branch: str | None = None,
        note: str | None = None,
    ) -> EvidenceManifest:
        """Handle human-in-the-loop review decision."""
        manifest = self.locker.load_manifest(run_id)
        if manifest.status != RunStatus.AWAITING_REVIEW:
            raise WorkflowStateError(
                f"Cannot review run '{run_id}' with status '{manifest.status.value}' (expected AWAITING_REVIEW)."
            )

        now = datetime.now(UTC).isoformat()

        if approve:
            patch = self.locker.load_patch(run_id)
            resulting_rev = activity_apply_patch(
                repo_path=manifest.repo_path,
                patch_content=patch,
                target_branch=target_branch,
                commit_msg=f"feat(dark-factory): applied verified patch from {run_id}",
            )
            manifest.status = RunStatus.APPROVED
            manifest.resulting_rev = resulting_rev
            manifest.operator_notes = note or "Approved by operator."
            self.transition_status(run_id, RunStatus.APPROVED, {"resulting_rev": resulting_rev})
        else:
            manifest.status = RunStatus.REJECTED
            manifest.operator_notes = note or "Rejected by operator."
            self.transition_status(run_id, RunStatus.REJECTED, {"note": manifest.operator_notes})

        manifest.completed_at = now
        self.locker.save_run(manifest, patch_content=self.locker.load_patch(run_id))

        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE runs
                SET status = ?, updated_at = ?, operator_notes = ?
                WHERE run_id = ?;
                """,
                (manifest.status.value, now, manifest.operator_notes, run_id),
            )

        return manifest

    def list_runs(self) -> list[dict]:
        """List all runs recorded in SQLite."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT run_id, repo_path, base_rev, status, created_at, updated_at, operator_notes FROM runs ORDER BY created_at DESC;"
            ).fetchall()
            return [dict(row) for row in rows]

    def get_run(self, run_id: str) -> EvidenceManifest:
        """Fetch full evidence manifest for a run."""
        return self.locker.load_manifest(run_id)

    def recover(self) -> list[str]:
        """Recover orphaned runs and clean up dead sandboxes."""
        recovered = []
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT run_id FROM runs
                WHERE status NOT IN ('APPROVED', 'REJECTED', 'FAILED', 'TIMED_OUT', 'CANCELLED');
                """
            ).fetchall()
            for row in rows:
                rid = row["run_id"]
                self.transition_status(rid, RunStatus.FAILED, {"reason": "Engine restart recovery"})
                recovered.append(rid)

        # Cleanup sandbox folder
        sandboxes_dir = self.storage_dir / "sandboxes"
        if sandboxes_dir.exists():
            import shutil

            for child in sandboxes_dir.iterdir():
                shutil.rmtree(child, ignore_errors=True)

        return recovered
