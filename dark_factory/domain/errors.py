"""Domain error definitions for Sovereign Dark Factory."""


class DarkFactoryError(Exception):
    """Base exception for all Dark Factory errors."""


class SandboxError(DarkFactoryError):
    """Raised when sandbox creation, command execution, or teardown fails."""


class WorktreeCreationError(SandboxError):
    """Raised when git worktree creation fails."""


class WorktreeCleanupError(SandboxError):
    """Raised when git worktree destruction fails."""


class HarnessError(DarkFactoryError):
    """Raised when an agent harness fails to invoke or communicate with local models."""


class LocalEngineOfflineError(HarnessError):
    """Raised when Ollama, Prism, or Foundry Local are unreachable."""


class VerificationFailedError(DarkFactoryError):
    """Raised when deterministic verification gates fail and maximum healing retries are exceeded."""


class WorkflowStateError(DarkFactoryError):
    """Raised on invalid workflow state transitions or journal corruption."""


class RunNotFoundError(DarkFactoryError):
    """Raised when attempting to inspect or review a non-existent run ID."""
