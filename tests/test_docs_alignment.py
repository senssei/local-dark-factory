"""Guards for the Phase 10.7 doc/code alignment decisions (plan.md §10.7)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIRRORS = {
    "intent.md": "docs/sdlc/intent.md",
    "spec.md": "docs/sdlc/spec.md",
    "CLAUDE.md": "docs/sdlc/claude.md",
    "AGENTS.md": "docs/sdlc/agents.md",
    "REVIEW.md": "docs/sdlc/review.md",
}


def _scanned_files() -> list[Path]:
    """Shipped docs and source; plan.md and CHANGELOG.md are history, not claims."""
    names = ("README.md", "intent.md", "spec.md", "CLAUDE.md", "AGENTS.md", "mkdocs.yml", "pyproject.toml")
    files = [ROOT / name for name in names]
    files += sorted((ROOT / "docs").rglob("*.md"))
    files += sorted((ROOT / "dark_factory").rglob("*.py"))
    return [f for f in files if f.is_file()]


def _hits(pattern: str, *, flags: int = 0) -> list[str]:
    regex = re.compile(pattern, flags)
    return [
        f"{path.relative_to(ROOT)}:{n}: {line.strip()}"
        for path in _scanned_files()
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if regex.search(line)
    ]


def test_no_foundry_backend_references():
    # The `foundry-coder` operator skill may be named; Foundry as an engine or backend may not.
    assert _hits(r"foundry(?!-coder)", flags=re.IGNORECASE) == []


def test_docker_sandbox_is_non_goal():
    lines = (ROOT / "intent.md").read_text(encoding="utf-8").splitlines()
    non_goals = next(i for i, line in enumerate(lines) if line.startswith("## 4. Non-Goals"))
    outside = [n + 1 for n, line in enumerate(lines) if "DockerSandbox" in line and n < non_goals]
    assert outside == []
    assert any("DockerSandbox" in line for line in lines[non_goals:])
    assert [h for h in _hits(r"DockerSandbox") if not h.startswith(("intent.md", "docs/sdlc/intent.md"))] == []


def test_temporal_is_described_as_seam():
    seam = "forward-looking seam"
    assert seam in (ROOT / "docs/architecture.md").read_text(encoding="utf-8")
    assert seam in (ROOT / "dark_factory/orchestrator/activities.py").read_text(encoding="utf-8")
    assert seam in (ROOT / "intent.md").read_text(encoding="utf-8")
    assert _hits(r"registered as Temporal Activities") == []


def test_no_unverified_performance_claims():
    # Latency / reliability numbers with no benchmark behind them (plan.md §10.7).
    assert _hits(r"\b100\s?ms|sub-?millisecond|zero memory leaks", flags=re.IGNORECASE) == []


def test_docs_sdlc_mirrors_match_root_files():
    for root_name, mirror in MIRRORS.items():
        assert (ROOT / root_name).read_bytes() == (ROOT / mirror).read_bytes(), f"{mirror} drifted from {root_name}"
