"""Sandbox execution fabric abstraction for Sovereign Dark Factory."""

from __future__ import annotations

from abc import ABC, abstractmethod

from dark_factory.domain.types import StepExecution


class Sandbox(ABC):
    """Abstract execution environment for running code agents and verification gates."""

    @abstractmethod
    def create(self, base_rev: str = "HEAD") -> None:
        """Initialize and isolate the sandbox at the specified revision."""

    @abstractmethod
    def execute(
        self,
        argv: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int = 300,
        step_id: str = "exec",
    ) -> StepExecution:
        """Execute a structured command inside the sandbox."""

    @abstractmethod
    def read_file(self, rel_path: str) -> bytes:
        """Read file contents relative to the sandbox root."""

    @abstractmethod
    def write_file(self, rel_path: str, content: bytes) -> None:
        """Write file contents relative to the sandbox root, creating parents if needed."""

    @abstractmethod
    def get_diff(self) -> str:
        """Extract a clean unified git diff of all modifications made in the sandbox."""

    @abstractmethod
    def restore_paths(self, paths: list[str], rev: str | None = None) -> list[str]:
        """Restore specified paths to their baseline state at the given revision.

        Returns the list of paths that were actually modified and restored.
        """

    @abstractmethod
    def destroy(self) -> None:
        """Tear down and destroy the sandbox idempotently."""

    def __enter__(self) -> Sandbox:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.destroy()
