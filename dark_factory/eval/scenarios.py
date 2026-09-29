"""Standardized real-model evaluation scenarios.

Each `build_*_repo` function scaffolds a throwaway git repository with one specific, known bug at a given
path. These are the same scaffolds used by the real-model end-to-end tests in `tests/test_e2e.py`
(`target_repo`, `calculator_repo`, `textutils_repo`, `csvparse_repo` fixtures) — extracted here so both the
pytest fixtures and the standalone `dark-factory eval` CLI share one implementation instead of two.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from dark_factory.domain.types import VerificationStep

_BROKEN_PRIMES = "def is_prime(n: int) -> bool:\n    return False  # TODO: implement\n"


def _git_init(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "AI Factory"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "factory@sovereign.local"], cwd=repo, check=True, capture_output=True
    )
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True, capture_output=True)


def _git_commit(repo: Path, message: str) -> None:
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=repo, check=True, capture_output=True)


def build_primes_repo(repo_path: Path) -> None:
    """A `primes.py` with a broken `is_prime` (always returns False) + `test_primes.py`."""
    repo_path.mkdir(parents=True, exist_ok=True)
    _git_init(repo_path)

    (repo_path / "primes.py").write_text(_BROKEN_PRIMES)
    (repo_path / "test_primes.py").write_text(
        "from primes import is_prime\n\n"
        "def test_is_prime():\n"
        "    assert is_prime(2) is True\n"
        "    assert is_prime(3) is True\n"
        "    assert is_prime(4) is False\n"
        "    assert is_prime(17) is True\n"
    )

    _git_commit(repo_path, "chore: initial broken prime calculator")


def build_calculator_repo(repo_path: Path) -> None:
    """A two-file repo (`calculator.py` missing `multiply`, `cli.py`'s `dispatch()` missing the branch)."""
    repo_path.mkdir(parents=True, exist_ok=True)
    _git_init(repo_path)

    (repo_path / "calculator.py").write_text(
        "def add(a, b):\n    return a + b\n\n\ndef subtract(a, b):\n    return a - b\n\n\n"
        "# TODO: implement multiply(a, b)\n"
    )
    (repo_path / "cli.py").write_text(
        "from calculator import add, subtract\n\n\n"
        "def dispatch(op, a, b):\n"
        "    if op == 'add':\n"
        "        return add(a, b)\n"
        "    if op == 'subtract':\n"
        "        return subtract(a, b)\n"
        "    # TODO: wire up a 'multiply' branch once calculator.multiply exists\n"
        "    raise ValueError(f'unknown op: {op}')\n"
    )
    (repo_path / "test_calculator.py").write_text(
        "from calculator import multiply\n"
        "from cli import dispatch\n\n\n"
        "def test_multiply():\n"
        "    assert multiply(3, 4) == 12\n\n\n"
        "def test_dispatch_multiply():\n"
        "    assert dispatch('multiply', 3, 4) == 12\n"
    )

    _git_commit(repo_path, "chore: calculator missing multiply")


def build_textutils_repo(repo_path: Path) -> None:
    """An existing `slugify()` with a whitespace-collapsing bug (naive `.replace(' ', '-')`)."""
    repo_path.mkdir(parents=True, exist_ok=True)
    _git_init(repo_path)

    (repo_path / "text_utils.py").write_text(
        "def slugify(text: str) -> str:\n"
        '    """Convert text to a URL-friendly slug: lowercase, words separated by a single hyphen."""\n'
        "    slug = text.strip().lower().replace(' ', '-')\n"
        "    return slug\n"
    )
    (repo_path / "test_text_utils.py").write_text(
        "from text_utils import slugify\n\n\n"
        "def test_slugify_basic():\n"
        "    assert slugify('Hello World') == 'hello-world'\n\n\n"
        "def test_slugify_collapses_repeated_whitespace():\n"
        "    assert slugify('Hello   World') == 'hello-world'\n\n\n"
        "def test_slugify_strips_leading_trailing_spaces():\n"
        "    assert slugify('  Hello World  ') == 'hello-world'\n"
    )

    _git_commit(repo_path, "chore: text_utils has a whitespace-collapsing bug")


def build_csvparse_repo(repo_path: Path) -> None:
    """A naive `parse_csv_line` (`line.split(',')`) that needs quote-aware CSV field parsing."""
    repo_path.mkdir(parents=True, exist_ok=True)
    _git_init(repo_path)

    (repo_path / "csvparse.py").write_text(
        "def parse_csv_line(line: str) -> list[str]:\n"
        '    """Parse a single CSV line into fields, respecting double-quoted fields (a doubled quote'
        ' \'""\' inside a quoted field is a literal quote character)."""\n'
        "    return line.split(',')\n"
    )
    (repo_path / "test_csvparse.py").write_text(
        "from csvparse import parse_csv_line\n\n\n"
        "def test_simple():\n"
        "    assert parse_csv_line('a,b,c') == ['a', 'b', 'c']\n\n\n"
        "def test_quoted_field_with_comma():\n"
        "    assert parse_csv_line('a,\"b,c\",d') == ['a', 'b,c', 'd']\n\n\n"
        "def test_quoted_field_with_escaped_quote():\n"
        "    assert parse_csv_line('a,\"b\"\"c\",d') == ['a', 'b\"c', 'd']\n"
    )

    _git_commit(repo_path, "chore: naive CSV parser, needs quote handling")


@dataclass(frozen=True)
class EvalScenario:
    """A named, reproducible real-model evaluation scenario."""

    name: str
    description: str
    build_repo: Callable[[Path], None]
    task_prompt: str
    verification_steps: Callable[[], list[VerificationStep]]
    protected_paths: list[str] = field(default_factory=list)
    max_healing_attempts: int = 5
    timeout_minutes: float = 5.0


SCENARIOS: dict[str, EvalScenario] = {
    "primes": EvalScenario(
        name="primes",
        description="Implement is_prime from a stub (single file, from-scratch).",
        build_repo=build_primes_repo,
        task_prompt="Implement correct is_prime logic in primes.py",
        verification_steps=lambda: [
            VerificationStep(id="pytest", argv=[sys.executable, "-m", "pytest", "test_primes.py"]),
        ],
        max_healing_attempts=3,
        timeout_minutes=5.0,
    ),
    "calculator": EvalScenario(
        name="calculator",
        description="Implement multiply() and wire it into a second file's dispatch() (multi-file edit).",
        build_repo=build_calculator_repo,
        task_prompt=(
            "Implement multiply(a, b) in calculator.py (it currently only has add and subtract), and add "
            "a 'multiply' branch to dispatch() in cli.py that calls it, so test_calculator.py passes."
        ),
        verification_steps=lambda: [
            VerificationStep(id="pytest", argv=[sys.executable, "-m", "pytest", "test_calculator.py"]),
        ],
        max_healing_attempts=5,
        timeout_minutes=5.0,
    ),
    "textutils": EvalScenario(
        name="textutils",
        description="Diagnose-and-fix a real bug in existing code, gated on pytest AND ruff check.",
        build_repo=build_textutils_repo,
        task_prompt=(
            "test_slugify_collapses_repeated_whitespace in test_text_utils.py is failing against "
            "text_utils.py's slugify() function. Fix the bug so all tests pass. Do not change the "
            "function signature."
        ),
        verification_steps=lambda: [
            VerificationStep(id="pytest", argv=[sys.executable, "-m", "pytest", "test_text_utils.py"]),
            VerificationStep(id="ruff", argv=[sys.executable, "-m", "ruff", "check", "text_utils.py"]),
        ],
        protected_paths=["test_text_utils.py"],
        max_healing_attempts=5,
        timeout_minutes=5.0,
    ),
    "csvparse": EvalScenario(
        name="csvparse",
        description="From-scratch quote-aware CSV parsing; genuinely exercises the self-healing loop.",
        build_repo=build_csvparse_repo,
        task_prompt=(
            "Implement parse_csv_line in csvparse.py so that test_csvparse.py passes. It must correctly "
            "handle double-quoted fields that contain commas, and a doubled quote '\"\"' inside a quoted "
            "field represents a single literal quote character."
        ),
        verification_steps=lambda: [
            VerificationStep(id="pytest", argv=[sys.executable, "-m", "pytest", "test_csvparse.py"]),
        ],
        max_healing_attempts=5,
        timeout_minutes=5.0,
    ),
}
