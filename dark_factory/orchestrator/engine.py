"""Durable SQLite workflow engine for Sovereign Dark Factory."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
import uuid
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from dark_factory.domain.errors import RunTimeoutError, WorkflowStateError
from dark_factory.domain.types import (
    EvidenceManifest,
    ModelTelemetry,
    PhaseTiming,
    RunStatus,
    StepExecution,
    TaskSpec,
)
from dark_factory.harness.base import AgentHarness
from dark_factory.harness.local_coder import LocalCoderHarness
from dark_factory.orchestrator.activities import (
    activity_adversarial_audit,
    activity_adversarial_mutation,
    activity_apply_patch,
    activity_cleanup_sandbox,
    activity_create_sandbox,
    activity_execute_task_and_verify,
    activity_plan_task,
    activity_preserve_evidence,
)
from dark_factory.storage.evidence import EvidenceLocker

# Statuses recover() must leave untouched: terminal outcomes plus AWAITING_REVIEW, which is a
# normal resting state (pending human review), not an orphan. Derived from RunStatus.is_terminal
# so a newly added in-flight status is picked up as an orphan automatically.
_NON_ORPHAN_STATUSES = frozenset(s.value for s in RunStatus if s.is_terminal) | {RunStatus.AWAITING_REVIEW.value}


@contextmanager
def _trace(manifest: EvidenceManifest, phase: str) -> Generator[None, None, None]:
    """Record a named phase's wall-clock duration onto the manifest.

    This is the whole tracing mechanism: no external backend, just timings alongside the rest of the
    evidence (consistent with Zero Cloud Tokens / local-first). Runs in `finally` so a phase that raises
    (e.g. a timed-out `agent_and_verify`) still gets its elapsed time recorded before the exception
    propagates.
    """
    started_at = datetime.now(UTC).isoformat()
    start = time.monotonic()
    try:
        yield
    finally:
        manifest.phase_timings.append(
            PhaseTiming(phase=phase, duration_sec=round(time.monotonic() - start, 3), started_at=started_at)
        )


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
        # Serializes the git-mutating part of review_run's approve path: unlike sandboxes (one isolated
        # worktree per run), activity_apply_patch mutates the host repo's actual working tree directly, so
        # concurrent approvals against the same repo would race on `checkout -b`/`apply`/`commit`.
        # Per-process only — see plan.md 10.11 for the cross-process limitation.
        self._review_lock = threading.Lock()
        self._init_db()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

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
        operator_notes: str | None = None,
    ) -> None:
        """Atomically transition run status and record audit event."""
        now = datetime.now(UTC).isoformat()
        payload_json = json.dumps(payload or {})
        with self._get_connection() as conn:
            if operator_notes is not None:
                conn.execute(
                    """
                    UPDATE runs
                    SET status = ?, updated_at = ?, operator_notes = ?
                    WHERE run_id = ?;
                    """,
                    (new_status.value, now, operator_notes, run_id),
                )
            else:
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

        deadline = time.monotonic() + spec.timeout_minutes * 60
        sandbox = None
        executions: list[StepExecution] = []
        healing_attempts = 0
        telemetry: ModelTelemetry | None = None
        try:
            # 1. Create Sandbox
            update_state(RunStatus.CREATING_SANDBOX)
            with _trace(manifest, "sandbox_create"):
                sandbox = activity_create_sandbox(
                    spec=spec,
                    run_id=run_id,
                    base_dir=self.storage_dir / "sandboxes",
                )

            def finish_timed_out(timeout: RunTimeoutError) -> EvidenceManifest:
                manifest.status = RunStatus.TIMED_OUT
                manifest.operator_notes = f"Run exceeded its {spec.timeout_minutes:g} minute deadline."
                timeout_diff = self._best_effort_diff(sandbox)
                with _trace(manifest, "evidence_preserve"):
                    activity_preserve_evidence(
                        sandbox=sandbox,
                        locker=self.locker,
                        manifest=manifest,
                        executions=timeout.executions,
                        healing_attempts=timeout.healing_attempts,
                        telemetry=timeout.telemetry,
                        diff=timeout_diff,
                    )
                # The save above can't record its own duration; persist the now-complete phase_timings
                # (cheap: same patch content, no transcript arg so transcript.log is left untouched).
                self.locker.save_run(manifest, patch_content=timeout_diff)
                update_state(RunStatus.TIMED_OUT, {"reason": "deadline_exceeded"})
                return manifest

            # 2. Run Planning Session (if not skip_plan)
            plan = None
            if not spec.skip_plan:
                try:
                    with _trace(manifest, "task_planning"):
                        plan = activity_plan_task(
                            run_id=run_id,
                            spec=spec,
                            sandbox=sandbox,
                            manifest=manifest,
                            harness=harness,
                            deadline=deadline,
                        )
                except RunTimeoutError as timeout:
                    return finish_timed_out(timeout)

            # 3. Run Agent & Verification Loop
            update_state(RunStatus.AGENT_RUNNING)
            try:
                with _trace(manifest, "agent_and_verify"):
                    passed, healing_attempts, executions, telemetry, repeated_failure_streak = (
                        activity_execute_task_and_verify(
                            sandbox=sandbox,
                            harness=harness,
                            spec=spec,
                            status_callback=update_state,
                            deadline=deadline,
                            plan=plan,
                        )
                    )
                manifest.repeated_failure_streak = repeated_failure_streak
            except RunTimeoutError as timeout:
                return finish_timed_out(timeout)

            # 3. Assess Result. Verification exit codes decide; a no-op is never a success.
            with _trace(manifest, "diff_extract"):
                diff = sandbox.get_diff()
            final_status = RunStatus.AWAITING_REVIEW if passed else RunStatus.FAILED
            final_payload: dict | None = None
            if passed and not diff.strip():
                final_status = RunStatus.FAILED
                final_payload = {"reason": "empty_patch"}
                manifest.operator_notes = "Verification passed but the agent produced no changes (empty patch)."
            elif not passed:
                if repeated_failure_streak >= 1:
                    manifest.operator_notes = (
                        f"Verification failed after exhausting {healing_attempts} healing attempt(s); the "
                        f"same failure repeated identically for the last {repeated_failure_streak + 1} "
                        "attempts (the model got stuck on one approach rather than trying something "
                        "different)."
                    )
                else:
                    manifest.operator_notes = (
                        f"Verification failed after exhausting {healing_attempts} healing attempt(s); each "
                        "attempt failed differently."
                    )
            elif spec.mutate_adversarial:
                # 3.1. Active Adversarial Test Mutation Gate
                try:
                    with _trace(manifest, "adversarial_mutation"):
                        mut_passed, mut_attempts, mut_execs, mut_telem = activity_adversarial_mutation(
                            sandbox=sandbox,
                            harness=harness,
                            spec=spec,
                            manifest=manifest,
                            diff=diff,
                            status_callback=update_state,
                            deadline=deadline,
                            healing_attempts_so_far=healing_attempts,
                        )
                except RunTimeoutError as timeout:
                    timeout.executions = executions + timeout.executions
                    timeout.healing_attempts += healing_attempts
                    timeout.telemetry = timeout.telemetry or telemetry
                    return finish_timed_out(timeout)
                executions.extend(mut_execs)
                healing_attempts += mut_attempts
                if mut_telem and telemetry:
                    telemetry.prompt_tokens += mut_telem.prompt_tokens
                    telemetry.completion_tokens += mut_telem.completion_tokens
                    telemetry.total_tokens += mut_telem.total_tokens
                    telemetry.duration_sec = round(telemetry.duration_sec + mut_telem.duration_sec, 3)
                elif mut_telem:
                    telemetry = mut_telem

                if not mut_passed:
                    passed = False
                    final_status = RunStatus.FAILED
                    reverify_failed = any(ex.step_id.endswith(":reverify") and not ex.passed for ex in executions)
                    manifest.operator_notes = (
                        "Verification failed: baseline gates failed after the adversarial probe ran "
                        "(post-probe re-verification); the probe may have altered the sources."
                        if reverify_failed
                        else f"Verification failed: adversarial probe test failed after {healing_attempts} healing attempt(s)."
                    )
                else:
                    # Re-extract diff in case healing modified files
                    with _trace(manifest, "diff_extract"):
                        diff = sandbox.get_diff()
                    if not spec.skip_adversarial:
                        # 3.2. Adversarial Red-Team Audit Gate (on verified final diff)
                        gate_summary_lines = [
                            f"[{ex.step_id}] {'PASSED' if ex.passed else 'FAILED'}" for ex in executions
                        ]
                        try:
                            with _trace(manifest, "adversarial_audit"):
                                activity_adversarial_audit(
                                    spec=spec,
                                    diff=diff,
                                    manifest=manifest,
                                    harness=harness,
                                    gate_summary="\n".join(gate_summary_lines),
                                    deadline=deadline,
                                )
                        except RunTimeoutError as timeout:
                            timeout.executions = executions + timeout.executions
                            timeout.healing_attempts += healing_attempts
                            timeout.telemetry = timeout.telemetry or telemetry
                            return finish_timed_out(timeout)
            elif not spec.skip_adversarial:
                # 3.1. Adversarial Red-Team Audit Gate (only on verified, non-empty patches)
                gate_summary_lines = [f"[{ex.step_id}] {'PASSED' if ex.passed else 'FAILED'}" for ex in executions]
                try:
                    with _trace(manifest, "adversarial_audit"):
                        activity_adversarial_audit(
                            spec=spec,
                            diff=diff,
                            manifest=manifest,
                            harness=harness,
                            gate_summary="\n".join(gate_summary_lines),
                            deadline=deadline,
                        )
                except RunTimeoutError as timeout:
                    timeout.executions = executions + timeout.executions
                    timeout.healing_attempts += healing_attempts
                    timeout.telemetry = timeout.telemetry or telemetry
                    return finish_timed_out(timeout)

            # 4. Preserve evidence BEFORE the durable status transition, so a crash can never leave a
            #    review-pending run without its evidence (recover() reconciles the opposite window).
            manifest.status = final_status
            with _trace(manifest, "evidence_preserve"):
                activity_preserve_evidence(
                    sandbox=sandbox,
                    locker=self.locker,
                    manifest=manifest,
                    executions=executions,
                    healing_attempts=healing_attempts,
                    telemetry=telemetry,
                    diff=diff,
                )
            # The save above can't record its own duration; persist the now-complete phase_timings
            # (cheap: same patch content, no transcript arg so transcript.log is left untouched).
            self.locker.save_run(manifest, patch_content=diff)
            update_state(final_status, final_payload)

            return manifest

        except (KeyboardInterrupt, SystemExit) as interrupt:
            manifest.status = RunStatus.CANCELLED
            manifest.operator_notes = f"Run cancelled ({type(interrupt).__name__})."
            try:
                if sandbox is not None:
                    # Same evidence shape as any other terminal state: preserve whatever diff the
                    # harness had produced before the interrupt, not just the manifest/transcript.
                    cancel_diff = self._best_effort_diff(sandbox)
                    with _trace(manifest, "evidence_preserve"):
                        activity_preserve_evidence(
                            sandbox=sandbox,
                            locker=self.locker,
                            manifest=manifest,
                            executions=executions,
                            healing_attempts=healing_attempts,
                            telemetry=telemetry,
                            diff=cancel_diff,
                        )
                    # The save above can't record its own duration; persist the now-complete
                    # phase_timings (cheap: same patch content, no transcript arg).
                    self.locker.save_run(manifest, patch_content=cancel_diff)
                else:
                    self.locker.save_run(manifest, transcript=f"CANCELLED: {type(interrupt).__name__}")
                self.transition_status(run_id, RunStatus.CANCELLED, {"reason": type(interrupt).__name__})
            except Exception:
                pass  # never mask the interrupt; recover() will reconcile
            raise

        except Exception as e:
            import traceback

            tb = traceback.format_exc()
            update_state(RunStatus.FAILED, {"error": str(e), "traceback": tb})
            manifest.status = RunStatus.FAILED
            manifest.operator_notes = f"Run encountered unhandled error: {e}"
            self.locker.save_run(manifest, transcript=f"ERROR: {e}\n\nTRACEBACK:\n{tb}")
            raise
        finally:
            if sandbox is not None:
                activity_cleanup_sandbox(sandbox)

    @staticmethod
    def _best_effort_diff(sandbox) -> str:
        try:
            return sandbox.get_diff()
        except Exception:
            return ""

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
            if manifest.patch_sha256:
                actual_sha = hashlib.sha256(patch.encode("utf-8")).hexdigest()
                if actual_sha != manifest.patch_sha256:
                    raise WorkflowStateError(
                        f"Patch integrity check failed for run '{run_id}'! "
                        f"Expected SHA256 {manifest.patch_sha256}, got {actual_sha}."
                    )

            # Serialize the actual host-repo mutation: `git checkout -b` / `apply` / `commit` operate on
            # one shared working tree, so two approvals racing here would corrupt each other.
            with self._review_lock, _trace(manifest, "patch_apply"):
                resulting_rev = activity_apply_patch(
                    repo_path=manifest.repo_path,
                    patch_content=patch,
                    target_branch=target_branch,
                    commit_msg=f"feat(dark-factory): applied verified patch from {run_id}",
                )
            manifest.status = RunStatus.APPROVED
            manifest.resulting_rev = resulting_rev
            manifest.operator_notes = note or "Approved by operator."
            manifest.completed_at = now
            self.transition_status(
                run_id,
                RunStatus.APPROVED,
                payload={"resulting_rev": resulting_rev},
                operator_notes=manifest.operator_notes,
            )
        else:
            manifest.status = RunStatus.REJECTED
            manifest.operator_notes = note or "Rejected by operator."
            manifest.completed_at = now
            self.transition_status(
                run_id,
                RunStatus.REJECTED,
                payload={"note": manifest.operator_notes},
                operator_notes=manifest.operator_notes,
            )

        self.locker.save_run(manifest, patch_content=self.locker.load_patch(run_id))
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

    def _reconcile_orphan(self, run_id: str) -> None:
        """Settle a run whose process died: adopt its evidence's outcome if complete, else mark FAILED.

        Evidence is written before the DB transition, and manifest.json is written last and atomically, so a
        readable manifest with a matching patch digest proves the run really reached that outcome.
        """
        try:
            manifest = self.locker.load_manifest(run_id)
            if manifest.status == RunStatus.AWAITING_REVIEW:
                patch = self.locker.load_patch(run_id)
                digest = hashlib.sha256(patch.encode("utf-8")).hexdigest()
                if manifest.patch_sha256 and digest == manifest.patch_sha256:
                    self.transition_status(
                        run_id,
                        RunStatus.AWAITING_REVIEW,
                        {"reason": "Engine restart recovery: evidence complete"},
                    )
                    return
            elif manifest.status in (RunStatus.FAILED, RunStatus.TIMED_OUT, RunStatus.CANCELLED):
                self.transition_status(run_id, manifest.status, {"reason": "Engine restart recovery"})
                return
        except Exception:
            pass  # no readable evidence: fall through to FAILED
        self.transition_status(run_id, RunStatus.FAILED, {"reason": "Engine restart recovery"})

    def _reconcile_review_completeness(self, run_id: str) -> bool:
        """Detect a crash between `transition_status(APPROVED/REJECTED)` and the final `locker.save_run()`
        in `review_run()` (DB says the review concluded, but the manifest on disk never caught up).

        For APPROVED, the patch may already have been committed to the target branch by
        `activity_apply_patch` before the crash, so we must not re-derive or re-apply it; the only safe
        move is to surface the inconsistency as `FAILED` with an explanatory note so the operator checks
        the repository by hand. Returns True if an inconsistency was found and flagged.
        """
        with self._get_connection() as conn:
            row = conn.execute("SELECT status FROM runs WHERE run_id = ?;", (run_id,)).fetchone()
        if row is None:
            return False
        db_status = row["status"]

        try:
            manifest = self.locker.load_manifest(run_id)
        except Exception:
            manifest = None

        if db_status == RunStatus.APPROVED.value:
            complete = manifest is not None and manifest.status == RunStatus.APPROVED and manifest.resulting_rev
        elif db_status == RunStatus.REJECTED.value:
            complete = manifest is not None and manifest.status == RunStatus.REJECTED and manifest.completed_at
        else:
            return False
        if complete:
            return False

        self.transition_status(
            run_id,
            RunStatus.FAILED,
            {
                "reason": (
                    f"Engine restart recovery: {db_status} transition did not complete "
                    "(evidence write crashed); verify repository state manually before retrying."
                )
            },
        )
        return True

    def recover(self) -> list[str]:
        """Recover orphaned runs, clean their sandboxes, and prune git worktrees."""
        recovered = []
        affected_repos: set[str] = set()
        sandboxes_dir = self.storage_dir / "sandboxes"

        with self._get_connection() as conn:
            placeholders = ",".join("?" for _ in _NON_ORPHAN_STATUSES)
            rows = conn.execute(
                f"SELECT run_id, repo_path FROM runs WHERE status NOT IN ({placeholders});",
                tuple(_NON_ORPHAN_STATUSES),
            ).fetchall()
            for row in rows:
                rid = row["run_id"]
                repo_path = row["repo_path"]
                if repo_path:
                    affected_repos.add(repo_path)
                self._reconcile_orphan(rid)
                recovered.append(rid)

                # Prune dead sandbox folder for this run
                run_sandbox = sandboxes_dir / rid
                if run_sandbox.exists():
                    import shutil

                    shutil.rmtree(run_sandbox, ignore_errors=True)

            # Separately: catch runs whose DB status already reads APPROVED/REJECTED but whose evidence
            # never caught up (crash between transition_status and the final locker.save_run in review_run).
            review_rows = conn.execute(
                "SELECT run_id FROM runs WHERE status IN (?, ?);",
                (RunStatus.APPROVED.value, RunStatus.REJECTED.value),
            ).fetchall()

        for row in review_rows:
            rid = row["run_id"]
            if self._reconcile_review_completeness(rid):
                recovered.append(rid)

        # Prune git worktree metadata in affected repos
        for repo_str in affected_repos:
            repo_p = Path(repo_str)
            if repo_p.exists():
                import subprocess

                subprocess.run(["git", "worktree", "prune"], cwd=repo_p, check=False, capture_output=True)

        return recovered
