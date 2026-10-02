#!/usr/bin/env python3
"""Deterministic SDLC gate shared by every harness (Claude Code, Codex, Gemini CLI, Copilot, Cursor, CI).

Skills tell an agent *when* to run this; the checks themselves are declared in `sdlc.toml`, so the verdict
does not depend on
which agent runs them or on the project's language. Standard library only, Python 3.11+ (tomllib).

python3 scripts/sdlc_check.py                 # every check in sdlc.toml
python3 scripts/sdlc_check.py --only tests    # named checks only (repeatable); `changelog` if [changelog] is
configured
python3 scripts/sdlc_check.py --base origin/main
python3 scripts/sdlc_check.py --red TEST_ID ...   # red-first: these tests must FAIL now (uses [red].run)

Exit status: 0 when every selected check passed or was skipped (with --red: when every named test is red), 1
when a check failed,
2 for a bad configuration or arguments. POSIX only (Linux, macOS, WSL). On Python < 3.11 it re-runs itself
under a newer python3.x.

Each `run` goes through the shell by default. `shell = false` (project-wide at the top of sdlc.toml, or per
`[[check]]` / on
`[red]`) runs it as argv instead: no shell process, no metacharacter or `$VAR` expansion.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Tuple  # noqa: UP035 - bootstrap on Python <3.11

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    tomllib = None

DEFAULT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE = "main"
DEFAULT_RED_TIMEOUT_S = 60
MAX_OUTPUT_BYTES = 1_000_000  # keep the tail of a command's output; a runaway command must not fill memory
# Exit codes meaning no test ran: the shell could not start the command (126, 127),
# or the command was killed by a signal (negative when we
# started it directly; 128+N, i.e. 129..159, when a shell that survived reports it).
COULD_NOT_RUN = (126, 127, *range(129, 160))
KNOWN_KEYS = {
    "": {"base", "check", "changelog", "red", "shell"},
    "check": {"name", "run", "skip_if_missing", "timeout", "shell"},
    "changelog": {"file", "runtime_paths"},
    "red": {"run", "timeout", "not_found", "ignore", "shell"},
}
# Result: (status, detail) with status one of "pass", "fail", "skip".
Result = Tuple[str, str]  # noqa: UP006 - evaluated before interpreter bootstrap
_ERROR_LINE = re.compile(r"(error|exception|assert|fail)", re.IGNORECASE)


class ConfigError(Exception):
    pass


def _string_list(value, where: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"sdlc.toml: {where} must be a list of strings")
    return value


def _regex_list(value, where: str) -> list[str]:
    for pattern in _string_list(value, where):
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ConfigError(f"sdlc.toml: {where} has an invalid regex {pattern!r}: {exc}") from exc
    return value


def _positive_number(value, where: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ConfigError(f"sdlc.toml: {where} must be a positive number of seconds")


def _check_shell(value, where: str) -> None:
    if not isinstance(value, bool):
        raise ConfigError(f"sdlc.toml: {where} must be true or false")


def _check_argv(run: str, where: str) -> None:
    """`run` must split into at least one argv element under shell=false; checked at load time, not at run time."""
    try:
        argv = shlex.split(run)
    except ValueError as exc:
        raise ConfigError(f"sdlc.toml: {where} is not valid with shell=false: {exc}") from exc
    if not argv:
        raise ConfigError(f"sdlc.toml: {where} has no command to execute with shell=false")


def load_config(root: Path) -> dict:
    path = root / "sdlc.toml"
    if tomllib is None:
        raise ConfigError("sdlc_check.py needs Python 3.11+ (tomllib) and found no python3.11 or newer on PATH")
    try:
        with open(path, "rb") as fh:
            cfg = tomllib.load(fh)
    except FileNotFoundError:
        raise ConfigError(f"{path} not found (run install.py, then fill in sdlc.toml)") from None
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: invalid TOML: {exc}") from exc

    if "base" in cfg and not isinstance(cfg["base"], str):
        raise ConfigError("sdlc.toml: `base` must be a string")
    if "shell" in cfg:
        _check_shell(cfg["shell"], "`shell`")
    default_shell = cfg.get("shell", True)
    checks = cfg.get("check", [])
    if not isinstance(checks, list) or not all(isinstance(c, dict) for c in checks):
        raise ConfigError("sdlc.toml: checks are written as [[check]] tables")
    names = set()
    for i, check in enumerate(checks):
        name, run = check.get("name"), check.get("run")
        if not isinstance(name, str) or not name:
            raise ConfigError(f"sdlc.toml: [[check]] #{i + 1} needs a `name`")
        if not isinstance(run, str) or not run:
            raise ConfigError(f"sdlc.toml: check {name!r} needs a `run` command")
        if "skip_if_missing" in check and not isinstance(check["skip_if_missing"], str):
            raise ConfigError(f"sdlc.toml: check {name!r}: `skip_if_missing` must be a string")
        if "timeout" in check:
            _positive_number(check["timeout"], f"check {name!r}: `timeout`")
        if "shell" in check:
            _check_shell(check["shell"], f"check {name!r}: `shell`")
        if not check.get("shell", default_shell):
            _check_argv(run, f"check {name!r}: `run`")
        if name in names or (name == "changelog" and "changelog" in cfg):
            raise ConfigError(f"sdlc.toml: duplicate check name {name!r}")
        names.add(name)
    if "changelog" in cfg:
        cl = cfg["changelog"]
        if not isinstance(cl, dict) or not isinstance(cl.get("file"), str) or "runtime_paths" not in cl:
            raise ConfigError("sdlc.toml: [changelog] needs `file` (string) and `runtime_paths` (list of strings)")
        paths = _string_list(cl["runtime_paths"], "[changelog].runtime_paths")
        if not cl["file"].strip() or not all(p.strip() for p in paths):
            raise ConfigError("sdlc.toml: [changelog].file and every entry of runtime_paths must be a non-empty path")
    if "red" in cfg:
        red = cfg["red"]
        if not isinstance(red, dict) or not isinstance(red.get("run"), str) or "{id}" not in red["run"]:
            raise ConfigError("sdlc.toml: [red].run must be a command containing {id}")
        if "timeout" in red:
            _positive_number(red["timeout"], "[red].timeout")
        if "shell" in red:
            _check_shell(red["shell"], "[red].shell")
        if not red.get("shell", default_shell):
            _check_argv(red["run"], "[red].run")
        _regex_list(red.get("not_found", []), "[red].not_found")
        _regex_list(red.get("ignore", []), "[red].ignore")
    return cfg


def unknown_keys(cfg: dict) -> list[str]:
    """Keys sdlc.toml has that the runner does not read: a typo (`[chagelog]`, `not_foud`) would otherwise
    disable a check silently.
    """
    found = [f"[{k}]" if isinstance(v, dict) else f"`{k}`" for k, v in cfg.items() if k not in KNOWN_KEYS[""]]
    for section in ("changelog", "red"):
        if isinstance(cfg.get(section), dict):
            found += [f"`{k}` in [{section}]" for k in cfg[section] if k not in KNOWN_KEYS[section]]
    found += [
        f"`{k}` in [[check]] {c.get('name')!r}" for c in cfg.get("check", []) for k in c if k not in KNOWN_KEYS["check"]
    ]
    return found


def _kill_group(pid: int) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pid, signal.SIGKILL)


def _terminated(signum, _frame):
    raise SystemExit(128 + signum)


def _run_command(cmd, cwd: Path, timeout: float | None = None, env=None) -> tuple[int | None, str]:
    """Run `cmd` and return (exit code, or None on timeout; the tail of the combined output).

    `cmd` is a shell command string (run through the shell) or an argv list (run directly: sdlc.toml's `shell
    = false`, no shell,
    no metacharacter or `$VAR` expansion). An argv command that cannot be found or executed is reported the
    same way a shell
    reports it (127, 126) so callers do not need to know which mode ran.

    Output goes to a temporary file, not a pipe: a background child that inherited the pipe would otherwise
    keep us waiting long
    after the command and its timeout were done. The command's whole process group is killed when it times
    out, when it ends
    (nothing it left in the background survives it), and when this runner is interrupted or terminated.

    """
    shell = isinstance(cmd, str)
    with tempfile.TemporaryFile() as sink:
        try:
            proc = subprocess.Popen(
                cmd,
                shell=shell,
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=sink,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except FileNotFoundError as exc:
            return 127, str(exc)
        except OSError as exc:
            return 126, str(exc)
        timed_out = False
        try:
            previous = signal.signal(signal.SIGTERM, _terminated)
        except ValueError:  # not the main thread: cannot install a handler
            previous = None
        try:
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                _kill_group(proc.pid)
                proc.wait()
        finally:
            _kill_group(proc.pid)
            if previous is not None:
                signal.signal(signal.SIGTERM, previous)
        size = sink.seek(0, os.SEEK_END)
        sink.seek(max(0, size - MAX_OUTPUT_BYTES))
        out = sink.read().decode("utf-8", errors="replace")
    return (None if timed_out else proc.returncode), out


def _tail(text: str, lines: int = 25) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def _last_line(text: str, width: int = 200) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1][:width] if lines else ""


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def _norm(path: str) -> str:
    return os.path.normpath(path)


def _under(path: str, prefix: str) -> bool:
    """`path` is `prefix` or lies below it, on a directory boundary (`src` does not cover `src_old/`)."""
    return prefix == "." or path == prefix or path.startswith(prefix.rstrip("/") + "/")


def changed_files(base: str, cwd: Path) -> tuple[str, object, str]:
    """Files under `cwd` changed relative to `base` (committed, staged, unstaged) plus untracked ones.

    Returns (status, payload, note): ("ok", [paths relative to cwd], note), ("skip", reason, "") when there is
    genuinely nothing to
    compare (git is missing, not a checkout, no commits yet), or ("fail", reason, "") when git could not
    answer or `base` cannot be
    resolved. Only the states above may skip: any other git error is a failure, or the gate would switch
    itself off silently.
    NUL-separated (-z) so paths with spaces or non-ASCII characters come back verbatim instead of quoted.
    Renames are reported as a
    deletion plus an addition (--no-renames) so a file moved out of a runtime path still counts.

    """
    try:
        inside = _git(["rev-parse", "--is-inside-work-tree"], cwd)
        if inside.returncode != 0:
            if "not a git repository" in inside.stderr:
                return "skip", "not a git checkout", ""
            return "fail", "git failed: " + _last_line(inside.stderr), ""
        head = _git(["rev-parse", "--verify", "HEAD^{commit}"], cwd)
        if head.returncode != 0:
            refs = _git(["for-each-ref", "--count=1"], cwd)
            if refs.returncode == 0 and not refs.stdout.strip():
                return "skip", "no commits yet", ""
            return (
                "fail",
                "git cannot read HEAD: "
                + (_last_line(head.stderr + refs.stderr) or "unreadable or corrupt repository"),
                "",
            )
        mb = _git(["merge-base", base, "HEAD"], cwd)
        if mb.returncode != 0:
            return (
                "fail",
                f"cannot diff against {base!r} (no such ref, or no common history): "
                "set `base` in sdlc.toml or pass --base REF",
                "",
            )
        diff = _git(["diff", "--name-only", "--no-renames", "--relative", "-z", mb.stdout.strip()], cwd)
        untracked = _git(["ls-files", "--others", "--exclude-standard", "-z"], cwd)
    except FileNotFoundError:
        return "skip", "git is not installed", ""
    if diff.returncode != 0 or untracked.returncode != 0:
        return "fail", "git could not list the changed files: " + _last_line(diff.stderr + untracked.stderr), ""
    files = sorted({*filter(None, diff.stdout.split("\0")), *filter(None, untracked.stdout.split("\0"))})
    note = (
        " (HEAD is the base: only uncommitted changes were compared)"
        if mb.stdout.strip() == head.stdout.strip()
        else ""
    )
    return "ok", files, note


def make_command_check(check: dict, root: Path, default_shell: bool = True) -> Callable[[str], Result]:
    shell = check.get("shell", default_shell)

    def run(base: str) -> Result:
        tool = check.get("skip_if_missing")
        if tool and shutil.which(tool) is None:
            return "skip", f"{tool} is not installed"
        timeout = check.get("timeout")
        cmd = check["run"] if shell else shlex.split(check["run"])
        env = dict(os.environ, SDLC_BASE=base)
        code, out = _run_command(cmd, root, timeout, env=env)
        if code is None:
            return "fail", f"timed out after {timeout:g}s\n" + _tail(out)
        return ("pass", _last_line(out)) if code == 0 else ("fail", _tail(out))

    return run


def make_changelog_check(cl: dict, root: Path) -> Callable[[str], Result]:
    """A change under `runtime_paths` needs a change to `file` (the changelog) as well."""
    prefixes = [_norm(p) for p in cl["runtime_paths"]]
    changelog = _norm(cl["file"])

    def run(base: str) -> Result:
        status, payload, note = changed_files(base, root)
        if status != "ok":
            return status, str(payload)
        code = [f for f in payload if any(_under(f, p) for p in prefixes)]
        if not code:
            return "pass", "no runtime code changed" + note
        if changelog in payload:
            return "pass", f"{len(code)} runtime file(s) changed, {cl['file']} updated"
        return "fail", f"runtime code changed but {cl['file']} was not touched:\n  " + "\n  ".join(code)

    return run


def build_checks(cfg: dict, root: Path) -> list[tuple[str, Callable[[str], Result]]]:
    default_shell = cfg.get("shell", True)
    checks = [(c["name"], make_command_check(c, root, default_shell)) for c in cfg.get("check", [])]
    if "changelog" in cfg:
        checks.append(("changelog", make_changelog_check(cfg["changelog"], root)))
    return checks


def _reason(output: str, ignore: list[re.Pattern]) -> str:
    """The most telling line of a failing test's output: the last line that looks like an error, else the last
    line.

    Lines matching `ignore` (the project's summary and decoration lines, from `[red].ignore`) are never
    chosen; they are matched
    with their indentation intact.

    """
    lines = [line.rstrip() for line in output.splitlines() if line.strip()]
    if not lines:
        return "(no output)"
    kept = [line for line in lines if not any(p.search(line) for p in ignore)] or lines
    for line in reversed(kept):
        if _ERROR_LINE.search(line):
            return line.strip()[:200]
    return kept[-1].strip()[:200]


def run_red(red: dict, test_ids: list[str], root: Path, default_shell: bool = True) -> tuple[bool, list[str]]:
    """Red-first check: True only if every named test really ran and failed, and exists."""
    if not test_ids:
        return False, ["no test ids given"]
    timeout = float(red.get("timeout", DEFAULT_RED_TIMEOUT_S))
    shell = red.get("shell", default_shell)
    not_found = [re.compile(p, re.MULTILINE) for p in red.get("not_found", [])]
    ignore = [re.compile(p, re.MULTILINE) for p in red.get("ignore", [])]
    lines: list[str] = []
    ok = True
    for tid in test_ids:
        if tid.startswith("-"):
            lines.append(f"NOT RED  {tid}: test id cannot start with '-' (runner option injection)")
            ok = False
            continue
        if shell:
            cmd = red["run"].replace("{id}", shlex.quote(tid))
        else:
            cmd = [tok.replace("{id}", tid) for tok in shlex.split(red["run"])]
        code, out = _run_command(cmd, root, timeout)
        if code is None:
            lines.append(f"NOT RED  {tid}: timed out after {timeout:g}s")
        elif code == 0:
            lines.append(f"NOT RED  {tid}: passes already, so it proves nothing")
        elif code < 0 or code in COULD_NOT_RUN:
            lines.append(
                f"NOT RED  {tid}: the test command could not run or was killed (exit {code}): {_reason(out, ignore)}"
            )
        elif any(p.search(out) for p in not_found):
            lines.append(f"NOT RED  {tid}: not found or not a test (check the id); output: {_reason(out, ignore)}")
        else:
            lines.append(f"RED      {tid}: {_reason(out, ignore)}")
            continue
        ok = False
    return ok, lines


def _reexec_with_newer_python(argv: list[str]) -> None:
    """Re-execute under the first Python >=3.11 on PATH; return only if none exists."""
    for minor in range(20, 10, -1):
        path = shutil.which(f"python3.{minor}")
        if path:
            os.execv(path, [path, str(Path(__file__).resolve()), *argv])  # noqa: S606 - interpreter re-exec
            return


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if tomllib is None:
        _reexec_with_newer_python(argv)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help="project root holding sdlc.toml (default: the parent of scripts/)",
    )
    ap.add_argument("--base", help="ref the diff is taken from (default: `base` in sdlc.toml, else main)")
    ap.add_argument("--only", action="append", metavar="NAME", help="run only this check (repeatable)")
    ap.add_argument(
        "--red", nargs="+", metavar="TEST_ID", help="expect these tests to fail now (red-first); runs no other check"
    )
    args = ap.parse_args(argv)
    root = args.root.resolve()

    if args.red is not None and (args.only or args.base):
        ap.error("--red runs no other check; drop --only / --base")
    try:
        cfg = load_config(root)
    except ConfigError as exc:
        print(f"sdlc_check: {exc}", file=sys.stderr)
        return 2
    for key in unknown_keys(cfg):
        print(
            f"sdlc_check: warning: sdlc.toml: unknown key {key} is ignored (a typo would disable it silently)",
            file=sys.stderr,
        )

    if args.red is not None:
        if "red" not in cfg:
            print("sdlc_check: --red needs a [red] section in sdlc.toml", file=sys.stderr)
            return 2
        ok, lines = run_red(cfg["red"], args.red, root, cfg.get("shell", True))
        print("\n".join(lines))
        return 0 if ok else 1

    checks = build_checks(cfg, root)
    if not checks:
        print("sdlc_check: sdlc.toml defines no checks (add a [[check]] or a [changelog] section)", file=sys.stderr)
        return 2
    known = [name for name, _ in checks]
    unknown = [n for n in args.only or [] if n not in known]
    if unknown:
        print(
            f"sdlc_check: unknown check {', '.join(map(repr, unknown))}; sdlc.toml defines: {', '.join(known)}",
            file=sys.stderr,
        )
        return 2

    failed = False
    ran = False
    for name, fn in checks:
        if args.only and name not in args.only:
            continue
        status, detail = fn(args.base or cfg.get("base", DEFAULT_BASE))
        ran = ran or status != "skip"
        print(
            f"[{status.upper():4}] {name}"
            + (f": {detail.splitlines()[0][:200]}" if detail and status != "fail" else "")
        )
        if status == "fail":
            failed = True
            if detail:
                print("\n".join("       " + line for line in detail.splitlines()))
    if not ran:
        print("warning: every selected check was skipped, nothing was verified")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
