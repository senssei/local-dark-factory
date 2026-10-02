"""Domain package for Sovereign Dark Factory."""

from dark_factory.domain.errors import (
    DarkFactoryError,
    HarnessError,
    LocalEngineOfflineError,
    RunNotFoundError,
    SandboxError,
    VerificationFailedError,
    WorkflowStateError,
    WorktreeCleanupError,
    WorktreeCreationError,
)
from dark_factory.domain.types import (
    AdversarialFinding,
    AdversarialReport,
    EvidenceManifest,
    ExecutionPlan,
    ModelTelemetry,
    RunStatus,
    StepExecution,
    TaskSpec,
    VerificationStep,
)

__all__ = [
    "AdversarialFinding",
    "AdversarialReport",
    "DarkFactoryError",
    "EvidenceManifest",
    "ExecutionPlan",
    "HarnessError",
    "LocalEngineOfflineError",
    "ModelTelemetry",
    "RunNotFoundError",
    "RunStatus",
    "SandboxError",
    "StepExecution",
    "TaskSpec",
    "VerificationFailedError",
    "VerificationStep",
    "WorkflowStateError",
    "WorktreeCleanupError",
    "WorktreeCreationError",
]
