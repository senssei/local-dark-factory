"""Deterministic performance & quality analysis of a verified run. No model calls, stdlib only."""

from __future__ import annotations

import ast
import codecs
import re
from pathlib import PurePosixPath

from dark_factory.domain.types import (
    AnalysisFinding,
    AnalysisReport,
    EvidenceManifest,
    ResourceUsage,
    TaskSpec,
)
from dark_factory.sandbox.base import Sandbox

# Defaults tuned for this workstation (RTX 5070 12 GB, 32 GB RAM).
VRAM_WARN_PCT = 90.0
RAM_WARN_PCT = 85.0
MIN_TOKENS_PER_SEC = 10.0
MAX_COMPLEXITY = 10
MAX_FUNCTION_LINES = 60
MAX_SOURCE_BYTES = 1_000_000  # larger files are not parsed

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _unquote_path(raw: str) -> str:
    """Normalise a diff header path: strip a trailing tab, unquote C-style quoting, drop the a/ b/ prefix."""
    raw = raw.strip("\t\n ")
    if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
        raw = codecs.escape_decode(raw[1:-1].encode("utf-8"))[0].decode("utf-8", "replace")
    return raw[2:] if raw[:2] in ("a/", "b/") else raw


def parse_diff(diff_text: str) -> tuple[dict[str, set[int]], int]:
    """Return ({path: added line numbers in the new file}, removed line count).

    Hunk line counts from the `@@` header decide what is content, so added or removed lines that
    merely look like `---` / `+++` headers are never mistaken for file headers.
    """
    added: dict[str, set[int]] = {}
    removed = 0
    old_path: str | None = None
    path: str | None = None
    lineno = 0
    old_rem = new_rem = 0
    for line in diff_text.splitlines():
        if old_rem > 0 or new_rem > 0:
            if line.startswith("+"):
                if path is not None:
                    added[path].add(lineno)
                lineno += 1
                new_rem -= 1
            elif line.startswith("-"):
                removed += 1
                old_rem -= 1
            elif line.startswith("\\"):
                continue
            else:
                lineno += 1
                old_rem -= 1
                new_rem -= 1
            continue
        if line.startswith("diff --git"):
            old_path = path = None
        elif line.startswith("--- "):
            old_path = None if line[4:].strip() == "/dev/null" else _unquote_path(line[4:])
        elif line.startswith("+++ "):
            path = None if line[4:].strip() == "/dev/null" else _unquote_path(line[4:])
            target = path or old_path  # a deleted file still counts as a changed file
            if target is not None:
                added.setdefault(target, set())
        elif line.startswith("rename to "):
            path = _unquote_path(line[len("rename to ") :])
            added.setdefault(path, set())
        elif m := _HUNK.match(line):
            lineno = int(m.group(3))
            old_rem = int(m.group(2) if m.group(2) is not None else 1)
            new_rem = int(m.group(4) if m.group(4) is not None else 1)
    return added, removed


def _is_test_path(path: str) -> bool:
    p = PurePosixPath(path)
    return bool({"tests", "test"} & set(p.parts[:-1])) or p.name.startswith("test_") or p.name.endswith("_test.py")


def _complexity(node: ast.AST) -> int:
    score = 1
    for child in ast.walk(node):
        if isinstance(
            child, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.IfExp, ast.comprehension)
        ):
            score += 1
        elif isinstance(child, ast.BoolOp):
            score += len(child.values) - 1
        elif isinstance(child, ast.match_case):
            score += 1
    return score


def _judge_functions(path: str, source: str, added_lines: set[int], findings: list[AnalysisFinding]) -> int:
    """Flag changed functions that are too complex or too long; return the max complexity seen."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0
    worst = 0
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        end = node.end_lineno or node.lineno
        if not any(node.lineno <= n <= end for n in added_lines):
            continue
        score = _complexity(node)
        length = end - node.lineno + 1
        worst = max(worst, score)
        if score > MAX_COMPLEXITY:
            findings.append(
                AnalysisFinding(
                    "WARN",
                    "quality",
                    f"{node.name} has cyclomatic complexity {score} (> {MAX_COMPLEXITY})",
                    f"{path}:{node.lineno}",
                )
            )
        if length > MAX_FUNCTION_LINES:
            findings.append(
                AnalysisFinding(
                    "WARN",
                    "quality",
                    f"{node.name} is {length} lines long (> {MAX_FUNCTION_LINES})",
                    f"{path}:{node.lineno}",
                )
            )
    return worst


def collect_sources(sandbox: Sandbox, diff_text: str) -> dict[str, str]:
    """Read the post-patch content of changed Python files; unreadable files are skipped."""
    sources: dict[str, str] = {}
    for path in parse_diff(diff_text)[0]:
        if not path.endswith(".py"):
            continue
        try:
            data = sandbox.read_file(path)
            if len(data) <= MAX_SOURCE_BYTES:
                sources[path] = data.decode("utf-8")
        except Exception:
            continue
    return sources


def analyze(
    manifest: EvidenceManifest,
    diff_text: str,
    spec: TaskSpec,
    resources: ResourceUsage,
    sources: dict[str, str] | None = None,
) -> AnalysisReport:
    """Build an advisory report. `sources` maps changed file paths to their post-patch content."""
    findings: list[AnalysisFinding] = []
    metrics: dict[str, object] = {}

    # Performance: phase breakdown, throughput, healing.
    total = sum(p.duration_sec for p in manifest.phase_timings)
    if manifest.phase_timings and total > 0:
        dominant = max(manifest.phase_timings, key=lambda p: p.duration_sec)
        pct = round(dominant.duration_sec / total * 100, 1)
        metrics["dominant_phase"] = dominant.phase
        metrics["dominant_phase_pct"] = pct
        findings.append(
            AnalysisFinding("INFO", "performance", f"Slowest phase: {dominant.phase} ({pct}% of {total:.1f}s)")
        )
    telemetry = manifest.model_telemetry
    if telemetry is not None and telemetry.tokens_per_sec > 0:
        metrics["tokens_per_sec"] = telemetry.tokens_per_sec
        if telemetry.tokens_per_sec < MIN_TOKENS_PER_SEC:
            findings.append(
                AnalysisFinding(
                    "WARN",
                    "performance",
                    f"Low throughput: {telemetry.tokens_per_sec:.1f} tok/s (< {MIN_TOKENS_PER_SEC:g})",
                    "The model may be partly offloaded to CPU; check `dark-factory doctor` and VRAM.",
                )
            )
    metrics["healing_attempts"] = manifest.healing_attempts
    if spec.max_healing_attempts > 0 and manifest.healing_attempts >= spec.max_healing_attempts:
        findings.append(
            AnalysisFinding(
                "WARN",
                "performance",
                f"Self-healing used all {spec.max_healing_attempts} attempts",
                "The patch only just converged; the task may be too large for the model.",
            )
        )

    # Resources.
    if resources.peak_vram_mb is not None and resources.vram_total_mb:
        pct = resources.peak_vram_mb / resources.vram_total_mb * 100
        if pct > VRAM_WARN_PCT:
            findings.append(
                AnalysisFinding(
                    "WARN",
                    "resources",
                    f"Peak VRAM {pct:.0f}% (> {VRAM_WARN_PCT:g}%)",
                    f"{resources.peak_vram_mb:.0f}/{resources.vram_total_mb:.0f} MiB; risk of offload to CPU.",
                )
            )
    if resources.peak_ram_mb is not None and resources.ram_total_mb:
        pct = resources.peak_ram_mb / resources.ram_total_mb * 100
        if pct > RAM_WARN_PCT:
            findings.append(
                AnalysisFinding(
                    "WARN",
                    "resources",
                    f"Peak RAM {pct:.0f}% (> {RAM_WARN_PCT:g}%)",
                    f"{resources.peak_ram_mb:.0f}/{resources.ram_total_mb:.0f} MiB.",
                )
            )

    # Quality: diff size, changed-function complexity/length, tests present.
    added, removed = parse_diff(diff_text)
    metrics["files_changed"] = len(added)
    metrics["lines_added"] = sum(len(lines) for lines in added.values())
    metrics["lines_removed"] = removed
    max_complexity = 0
    for path, lines in added.items():
        if path.endswith(".py") and sources and path in sources:
            max_complexity = max(max_complexity, _judge_functions(path, sources[path], lines, findings))
    if max_complexity:
        metrics["max_complexity"] = max_complexity
    py_files = [p for p in added if p.endswith(".py")]
    if any(not _is_test_path(p) for p in py_files) and not any(_is_test_path(p) for p in added):
        findings.append(
            AnalysisFinding("WARN", "quality", "Source changed without tests", "No test file appears in the patch.")
        )

    warns = sum(1 for f in findings if f.severity == "WARN")
    summary = f"{warns} warning(s); {metrics['files_changed']} file(s), +{metrics['lines_added']}/-{removed} lines"
    return AnalysisReport(summary=summary, resources=resources, findings=findings, metrics=metrics)
