"""Agent harness interface for Sovereign Dark Factory."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from dark_factory.domain.types import ModelTelemetry
from dark_factory.sandbox.base import Sandbox


@dataclass
class HarnessResult:
    """Result of an agent harness execution."""

    success: bool
    modified_files: list[str] = field(default_factory=list)
    telemetry: ModelTelemetry | None = None
    raw_response: str = ""
    error: str | None = None


class AgentHarness(ABC):
    """Abstract agent harness for running coding agents inside sandboxes."""

    @abstractmethod
    def execute_task(
        self,
        sandbox: Sandbox,
        task_prompt: str,
        target_files: list[str] | None = None,
    ) -> HarnessResult:
        """Apply code changes to the sandbox to accomplish the task."""
