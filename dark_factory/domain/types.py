"""Domain data contracts and types for Sovereign Dark Factory."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class RunStatus(StrEnum):
    """Lifecycle status of a dark factory run."""

    PENDING = "PENDING"
    CREATING_SANDBOX = "CREATING_SANDBOX"
    AGENT_RUNNING = "AGENT_RUNNING"
    VERIFYING = "VERIFYING"
    SELF_HEALING = "SELF_HEALING"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"

    @property
    def is_terminal(self) -> bool:
        return self in (
            RunStatus.APPROVED,
            RunStatus.REJECTED,
            RunStatus.FAILED,
            RunStatus.TIMED_OUT,
            RunStatus.CANCELLED,
        )


@dataclass(frozen=True)
class VerificationStep:
    """A single deterministic verification gate."""

    id: str
    argv: list[str]
    timeout_sec: int = 300
    mandatory: bool = True
    description: str = ""


@dataclass
class StepExecution:
    """Outcome of a single verification step or command execution."""

    step_id: str
    exit_code: int
    stdout: str
    stderr: str
    duration_sec: float
    timed_out: bool = False

    @property
    def passed(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


@dataclass
class TaskSpec:
    """Specification for an autonomous coding task."""

    repo_path: str
    task_prompt: str
    base_rev: str = "HEAD"
    agent: str = "local-coder"
    model: str = "qwen2.5-coder:14b"
    verification_steps: list[VerificationStep] = field(default_factory=list)
    allow_no_verify: bool = False
    max_healing_attempts: int = 3
    timeout_minutes: int = 30
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelTelemetry:
    """Telemetry captured from local inference engines (Ollama / Prism / Foundry)."""

    engine: str
    model_name: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    duration_sec: float = 0.0
    tokens_per_sec: float = 0.0
    cost_usd: float = 0.0  # Always 0.0 for local models


@dataclass
class EvidenceManifest:
    """Immutable audit record and evidence of a completed or paused run."""

    run_id: str
    status: RunStatus
    repo_path: str
    base_rev: str
    created_at: str
    completed_at: str | None = None
    resulting_rev: str | None = None
    patch_path: str | None = None
    patch_size_bytes: int = 0
    healing_attempts: int = 0
    verification_results: list[StepExecution] = field(default_factory=list)
    model_telemetry: ModelTelemetry | None = None
    operator_notes: str | None = None

    @classmethod
    def create(
        cls,
        run_id: str,
        repo_path: str,
        base_rev: str,
        status: RunStatus = RunStatus.PENDING,
    ) -> EvidenceManifest:
        return cls(
            run_id=run_id,
            status=status,
            repo_path=repo_path,
            base_rev=base_rev,
            created_at=datetime.now(UTC).isoformat(),
        )
