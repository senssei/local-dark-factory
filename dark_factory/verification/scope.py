"""Deterministic patch-scope check: which files of a patch fall outside the task's scope."""

from __future__ import annotations

import posixpath


def _is_placeholder(path: str) -> bool:
    """True when two consecutive components are `path`, `to` (the prompt's `path/to/file.ext` example copied verbatim)."""
    parts = path.split("/")
    return any(a == "path" and b == "to" for a, b in zip(parts, parts[1:], strict=False))


def _in_targets(path: str, target_files: list[str]) -> bool:
    """A target covers a path equal to it or below it (so `pkg` and `pkg/` are the same directory); `.` covers everything."""
    for target in target_files:
        if not target:
            continue
        norm = posixpath.normpath(target)
        if norm == "." or path == norm or path.startswith(norm + "/"):
            return True
    return False


def check_patch_scope(paths: list[str], target_files: list[str]) -> list[str]:
    """Return the sorted, unique paths of a patch that are outside the task's scope.

    A path is out of scope when it is a placeholder (`path/to/...`), or when `target_files` is non-empty and the path
    is neither one of them nor below one (a target is a file or a directory; `.` is the whole repository).
    """
    offending = {p for p in paths if _is_placeholder(p) or (target_files and not _in_targets(p, target_files))}
    return sorted(offending)
