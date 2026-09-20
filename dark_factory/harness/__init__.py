"""Harness package for Sovereign Dark Factory."""

from dark_factory.harness.base import AgentHarness, HarnessResult
from dark_factory.harness.local_coder import LocalCoderHarness

__all__ = ["AgentHarness", "HarnessResult", "LocalCoderHarness"]
