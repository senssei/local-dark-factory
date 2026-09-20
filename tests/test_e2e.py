"""End-to-end acceptance test for Sovereign Dark Factory."""

import subprocess
import sys
from pathlib import Path

import pytest

from dark_factory.domain.types import (
    ModelTelemetry,
    RunStatus,
    TaskSpec,
    VerificationStep,
)
from dark_factory.harness.base import AgentHarness, HarnessResult
from dark_factory.orchestrator import DurableEngine
from dark_factory.sandbox.base import Sandbox


@pytest.fixture
def target_repo(tmp_path: Path) -> Path:
    """Create a realistic Python repository with a failing unit test."""
    repo = tmp_path / "prime_calculator"
    repo.mkdir()

    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "AI Factory"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "factory@sovereign.local"], cwd=repo, check=True, capture_output=True
    )
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True, capture_output=True)

    # Initial broken code
    (repo / "primes.py").write_text("def is_prime(n: int) -> bool:\n    return False  # TODO: implement\n")
    (repo / "test_primes.py").write_text(
        "from primes import is_prime\n\n"
        "def test_is_prime():\n"
        "    assert is_prime(2) is True\n"
        "    assert is_prime(3) is True\n"
        "    assert is_prime(4) is False\n"
        "    assert is_prime(17) is True\n"
    )

    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "chore: initial broken prime calculator"], cwd=repo, check=True, capture_output=True
    )
    return repo


class DeterministicPrimeHarness(AgentHarness):
    """Simulates local model implementing is_prime correctly."""

    def execute_task(self, sandbox: Sandbox, task_prompt: str, target_files=None):
        fixed_code = (
            "def is_prime(n: int) -> bool:\n"
            "    if n < 2:\n"
            "        return False\n"
            "    for i in range(2, int(n**0.5) + 1):\n"
            "        if n % i == 0:\n"
            "            return False\n"
            "    return True\n"
        )
        sandbox.write_file("primes.py", fixed_code.encode("utf-8"))
        return HarnessResult(
            success=True,
            modified_files=["primes.py"],
            telemetry=ModelTelemetry(
                engine="ollama",
                model_name="qwen2.5-coder:14b",
                prompt_tokens=85,
                completion_tokens=65,
                total_tokens=150,
                duration_sec=1.5,
                tokens_per_sec=43.3,
                cost_usd=0.0,
            ),
        )


def test_full_factory_vertical_slice(target_repo: Path, tmp_path: Path):
    storage = tmp_path / ".factory"
    engine = DurableEngine(storage_dir=storage)

    # 1. Verify baseline test fails
    baseline_check = subprocess.run(
        [sys.executable, "-m", "pytest", "test_primes.py"],
        cwd=target_repo,
        capture_output=True,
        text=True,
    )
    assert baseline_check.returncode != 0

    # 2. Submit task
    spec = TaskSpec(
        repo_path=str(target_repo),
        task_prompt="Implement correct is_prime logic in primes.py",
        verification_steps=[
            VerificationStep(id="pytest", argv=[sys.executable, "-m", "pytest", "test_primes.py"]),
        ],
    )

    manifest = engine.execute_run(
        spec=spec,
        harness=DeterministicPrimeHarness(),
        run_id="run-acceptance-primes",
    )

    # 3. Assert factory result
    assert manifest.status == RunStatus.AWAITING_REVIEW
    assert manifest.patch_size_bytes > 0
    assert manifest.healing_attempts == 0
    assert len(manifest.verification_results) == 1
    assert manifest.verification_results[0].passed
    assert manifest.model_telemetry.cost_usd == 0.0

    # 4. Human-In-The-Loop: Review & Approve
    approved = engine.review_run(
        run_id="run-acceptance-primes",
        approve=True,
        target_branch="feature/primes-implementation",
        note="Verified prime numbers algorithm",
    )

    assert approved.status == RunStatus.APPROVED

    # 5. Verify the repository now passes tests on the new branch!
    after_review_check = subprocess.run(
        [sys.executable, "-m", "pytest", "test_primes.py"],
        cwd=target_repo,
        capture_output=True,
        text=True,
    )
    assert after_review_check.returncode == 0
