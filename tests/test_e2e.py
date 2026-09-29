"""End-to-end acceptance tests for Sovereign Dark Factory.

Every test in this module goes through the real `DurableEngine.execute_run` (or, for the CLI tests,
a real `dark-factory` subprocess) with no orchestrator/sandbox/verification internals mocked. The only
test double is the agent harness (or, for the CLI tests, a stub HTTP server standing in for Ollama) —
mirroring how the local model is the one piece that can't be exercised deterministically in CI.
"""

import http.server
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from dark_factory.domain.errors import WorkflowStateError
from dark_factory.domain.types import (
    ModelTelemetry,
    RunStatus,
    TaskSpec,
    VerificationStep,
)
from dark_factory.eval.scenarios import (
    build_calculator_repo,
    build_csvparse_repo,
    build_primes_repo,
    build_textutils_repo,
)
from dark_factory.harness.base import AgentHarness, HarnessResult
from dark_factory.harness.local_coder import LocalCoderHarness
from dark_factory.orchestrator import DurableEngine
from dark_factory.sandbox.base import Sandbox

_BROKEN_PRIMES = "def is_prime(n: int) -> bool:\n    return False  # TODO: implement\n"
_FIXED_PRIMES = (
    "def is_prime(n: int) -> bool:\n"
    "    if n < 2:\n"
    "        return False\n"
    "    for i in range(2, int(n**0.5) + 1):\n"
    "        if n % i == 0:\n"
    "            return False\n"
    "    return True\n"
)


@pytest.fixture
def target_repo(tmp_path: Path) -> Path:
    """Create a realistic Python repository with a failing unit test."""
    repo = tmp_path / "prime_calculator"
    build_primes_repo(repo)
    return repo


class DeterministicPrimeHarness(AgentHarness):
    """Simulates local model implementing is_prime correctly."""

    def execute_task(self, sandbox: Sandbox, task_prompt: str, target_files=None):
        sandbox.write_file("primes.py", _FIXED_PRIMES.encode("utf-8"))
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


def _gate() -> list[VerificationStep]:
    return [VerificationStep(id="pytest", argv=[sys.executable, "-m", "pytest", "test_primes.py"])]


class SlowHarness(AgentHarness):
    """Simulates a local model that is still generating when the deadline hits."""

    def execute_task(self, sandbox: Sandbox, task_prompt: str, target_files=None):
        time.sleep(0.5)
        sandbox.write_file("primes.py", _FIXED_PRIMES.encode("utf-8"))
        return HarnessResult(success=True, modified_files=["primes.py"])


def test_e2e_run_deadline_produces_timed_out(target_repo: Path, tmp_path: Path):
    storage = tmp_path / ".factory"
    engine = DurableEngine(storage_dir=storage)
    spec = TaskSpec(
        repo_path=str(target_repo),
        task_prompt="Implement correct is_prime logic in primes.py",
        verification_steps=_gate(),
        timeout_minutes=0.004,  # ~0.24s, shorter than SlowHarness's 0.5s
    )

    manifest = engine.execute_run(spec=spec, harness=SlowHarness(), run_id="run-e2e-timeout")

    assert manifest.status == RunStatus.TIMED_OUT
    assert "deadline" in (manifest.operator_notes or "").lower()
    assert not (storage / "sandboxes" / "run-e2e-timeout").exists()
    # Evidence must still be readable end-to-end, not just held in-memory.
    reloaded = engine.get_run("run-e2e-timeout")
    assert reloaded.status == RunStatus.TIMED_OUT
    with pytest.raises(WorkflowStateError):
        engine.review_run("run-e2e-timeout", approve=True)


class WritesPartialFixThenInterrupts(AgentHarness):
    """Simulates an operator hitting Ctrl-C mid-generation, after a partial edit landed on disk."""

    def execute_task(self, sandbox: Sandbox, task_prompt: str, target_files=None):
        sandbox.write_file("primes.py", b"def is_prime(n: int) -> bool:\n    return True  # unfinished\n")
        raise KeyboardInterrupt


def test_e2e_cancellation_preserves_partial_diff(target_repo: Path, tmp_path: Path):
    storage = tmp_path / ".factory"
    engine = DurableEngine(storage_dir=storage)
    spec = TaskSpec(
        repo_path=str(target_repo),
        task_prompt="Implement correct is_prime logic in primes.py",
        verification_steps=_gate(),
    )

    with pytest.raises(KeyboardInterrupt):
        engine.execute_run(spec=spec, harness=WritesPartialFixThenInterrupts(), run_id="run-e2e-cancel")

    manifest = engine.get_run("run-e2e-cancel")
    assert manifest.status == RunStatus.CANCELLED
    assert manifest.patch_size_bytes > 0
    patch = engine.locker.load_patch("run-e2e-cancel")
    assert "unfinished" in patch
    assert not (storage / "sandboxes" / "run-e2e-cancel").exists()


class NoOpHarness(AgentHarness):
    """Claims success but rewrites primes.py with identical content (empty diff)."""

    def execute_task(self, sandbox: Sandbox, task_prompt: str, target_files=None):
        sandbox.write_file("primes.py", _BROKEN_PRIMES.encode("utf-8"))
        return HarnessResult(success=True, modified_files=["primes.py"])


def test_e2e_empty_patch_ends_failed_not_awaiting_review(target_repo: Path, tmp_path: Path):
    storage = tmp_path / ".factory"
    engine = DurableEngine(storage_dir=storage)
    # A trivially-passing gate: this scenario is about a no-op agent slipping past verification, not
    # about the (broken) primes.py actually failing test_primes.py.
    always_passing_gate = [VerificationStep(id="ok", argv=[sys.executable, "-c", "raise SystemExit(0)"])]
    spec = TaskSpec(repo_path=str(target_repo), task_prompt="do nothing useful", verification_steps=always_passing_gate)

    manifest = engine.execute_run(spec=spec, harness=NoOpHarness(), run_id="run-e2e-noop")

    assert manifest.status == RunStatus.FAILED
    assert "empty patch" in (manifest.operator_notes or "").lower()
    with pytest.raises(WorkflowStateError):
        engine.review_run("run-e2e-noop", approve=True)


class FailsOnceThenFixesHarness(AgentHarness):
    """First attempt ships a plausible-looking but still-wrong fix; the repair prompt gets it right."""

    def __init__(self) -> None:
        self.calls = 0

    def execute_task(self, sandbox: Sandbox, task_prompt: str, target_files=None):
        self.calls += 1
        if self.calls == 1:
            # Deliberately wrong first attempt. Byte size differs from _FIXED_PRIMES on purpose: a
            # same-size rewrite within the same filesystem mtime second can leave Python's compiled
            # .pyc cache (which keys on mtime+size, both second-granularity) stale, making the sandbox's
            # `pytest` subprocess re-run the OLD bytecode against the new source — a real but unrelated
            # footgun this fixture must not trip over.
            sandbox.write_file(
                "primes.py", b"def is_prime(n: int) -> bool:\n    return n > 100  # first attempt guess\n"
            )
        else:
            sandbox.write_file("primes.py", _FIXED_PRIMES.encode("utf-8"))
        return HarnessResult(success=True, modified_files=["primes.py"])


def test_e2e_self_healing_repairs_failing_verification(target_repo: Path, tmp_path: Path):
    storage = tmp_path / ".factory"
    engine = DurableEngine(storage_dir=storage)
    spec = TaskSpec(
        repo_path=str(target_repo),
        task_prompt="Implement correct is_prime logic in primes.py",
        verification_steps=_gate(),
    )

    manifest = engine.execute_run(spec=spec, harness=FailsOnceThenFixesHarness(), run_id="run-e2e-heal")

    assert manifest.status == RunStatus.AWAITING_REVIEW
    assert manifest.healing_attempts == 1
    approved = engine.review_run(run_id="run-e2e-heal", approve=True, target_branch="feature/healed-primes")
    assert approved.status == RunStatus.APPROVED

    after = subprocess.run(
        [sys.executable, "-m", "pytest", "test_primes.py"], cwd=target_repo, capture_output=True, text=True
    )
    assert after.returncode == 0


def test_e2e_recover_after_crash_completes_full_review_flow(target_repo: Path, tmp_path: Path):
    """A crash between evidence-save and the DB transition must still let the run reach APPROVED,
    not just show the right status in SQLite."""
    storage = tmp_path / ".factory"
    engine = DurableEngine(storage_dir=storage)
    spec = TaskSpec(
        repo_path=str(target_repo),
        task_prompt="Implement correct is_prime logic in primes.py",
        verification_steps=_gate(),
    )
    engine.execute_run(spec=spec, harness=DeterministicPrimeHarness(), run_id="run-e2e-crash")

    # Simulate the engine process dying after evidence was written but before the AWAITING_REVIEW
    # transition committed (10.3's "evidence before status" ordering means the manifest on disk is
    # already complete at this point).
    with engine._get_connection() as conn:
        conn.execute("UPDATE runs SET status='VERIFYING' WHERE run_id='run-e2e-crash';")

    recovered = engine.recover()
    assert "run-e2e-crash" in recovered
    assert engine.get_run("run-e2e-crash").status == RunStatus.AWAITING_REVIEW

    approved = engine.review_run(run_id="run-e2e-crash", approve=True, target_branch="feature/recovered-primes")
    assert approved.status == RunStatus.APPROVED

    after = subprocess.run(
        [sys.executable, "-m", "pytest", "test_primes.py"], cwd=target_repo, capture_output=True, text=True
    )
    assert after.returncode == 0


def _local_engine_available() -> tuple[bool, str]:
    """Mirror `dark-factory doctor`'s reachability check so this test skips cleanly without a GPU/local stack."""
    status = LocalCoderHarness().check_health()
    if status["ollama"]:
        return True, "ollama"
    if status["prism"]:
        return True, "prism"
    return False, ""


@pytest.mark.local_engine
def test_e2e_real_local_model_smoke(target_repo: Path, tmp_path: Path):
    """Exercises the real Ollama/Prism HTTP call instead of a stub harness, and requires the model to
    actually solve the task — not just that the pipeline didn't raise. Skips (does not fail) when neither
    local engine is reachable, so CI without a GPU/Ollama install stays green; run by hand on the
    operator's machine with `pytest -m local_engine`.
    """
    available, engine_name = _local_engine_available()
    if not available:
        pytest.skip("No local inference engine (Ollama/Prism) reachable on localhost.")

    storage = tmp_path / ".factory"
    engine = DurableEngine(storage_dir=storage)
    spec = TaskSpec(
        repo_path=str(target_repo),
        task_prompt="Implement correct is_prime logic in primes.py",
        verification_steps=_gate(),
        max_healing_attempts=3,
    )

    manifest = engine.execute_run(spec=spec, harness=LocalCoderHarness(), run_id="run-e2e-real-model")

    assert manifest.status == RunStatus.AWAITING_REVIEW, (
        f"Real model failed to solve a trivial task after {manifest.healing_attempts} healing attempt(s): "
        f"{manifest.operator_notes}"
    )
    assert manifest.model_telemetry is not None
    assert manifest.model_telemetry.engine == engine_name
    assert manifest.model_telemetry.cost_usd == 0.0

    approved = engine.review_run(run_id="run-e2e-real-model", approve=True, target_branch="feature/real-model-primes")
    assert approved.status == RunStatus.APPROVED

    after = subprocess.run(
        [sys.executable, "-m", "pytest", "test_primes.py"], cwd=target_repo, capture_output=True, text=True
    )
    assert after.returncode == 0, after.stdout + after.stderr


@pytest.fixture
def calculator_repo(tmp_path: Path) -> Path:
    """A two-file repo with one function and one call-site missing, so a correct fix must touch both
    files — a stub harness can fake this trivially, but a real model has to actually parse the task across
    files and emit two `` ```file: `` blocks."""
    repo = tmp_path / "calculator"
    build_calculator_repo(repo)
    return repo


@pytest.mark.local_engine
def test_e2e_real_local_model_multi_file_task(calculator_repo: Path, tmp_path: Path):
    """More realistic than the single-file smoke test: requires the real model to edit two files
    consistently (add `multiply` to calculator.py AND wire it into cli.py's dispatch) and actually pass,
    not just avoid crashing. Run by hand with `pytest -m local_engine`."""
    available, engine_name = _local_engine_available()
    if not available:
        pytest.skip("No local inference engine (Ollama/Prism) reachable on localhost.")

    storage = tmp_path / ".factory"
    engine = DurableEngine(storage_dir=storage)
    spec = TaskSpec(
        repo_path=str(calculator_repo),
        task_prompt=(
            "Implement multiply(a, b) in calculator.py (it currently only has add and subtract), and add "
            "a 'multiply' branch to dispatch() in cli.py that calls it, so test_calculator.py passes."
        ),
        verification_steps=[
            VerificationStep(id="pytest", argv=[sys.executable, "-m", "pytest", "test_calculator.py"]),
        ],
        max_healing_attempts=5,
        timeout_minutes=5,
    )

    manifest = engine.execute_run(spec=spec, harness=LocalCoderHarness(), run_id="run-e2e-real-model-multifile")

    assert manifest.status == RunStatus.AWAITING_REVIEW, (
        f"Real model failed the multi-file task after {manifest.healing_attempts} healing attempt(s): "
        f"{manifest.operator_notes}"
    )
    assert manifest.model_telemetry is not None
    assert manifest.model_telemetry.engine == engine_name

    approved = engine.review_run(
        run_id="run-e2e-real-model-multifile", approve=True, target_branch="feature/real-model-multiply"
    )
    assert approved.status == RunStatus.APPROVED

    after = subprocess.run(
        [sys.executable, "-m", "pytest", "test_calculator.py"], cwd=calculator_repo, capture_output=True, text=True
    )
    assert after.returncode == 0, after.stdout + after.stderr


@pytest.fixture
def textutils_repo(tmp_path: Path) -> Path:
    """An existing (not stubbed-out) module with one narrowly-scoped, genuine bug: `slugify` replaces a
    single space with a hyphen, so repeated whitespace produces repeated hyphens instead of one. One of
    three tests already passes — a correct fix must not regress it.

    Kept deliberately to a single function / single root cause: earlier iterations of this fixture also
    included a `truncate()` whose "correct" behavior (always append `...`, even past `max_length`) conflicts
    with the far more common "total length capped at max_length including the ellipsis" convention. Real
    runs against qwen2.5-coder:14b showed the model reliably "fixing" that unrelated, already-correct
    function anyway — even when explicitly told not to — because it strongly matches that convention. That
    is a genuine and useful finding about LLM behavior (strong training-data priors can override an explicit
    negative instruction), but it makes a *correctness* test flaky against model judgment calls rather than
    an objective bug. A single-function fixture with no such ambiguity is 3/3 reliable in manual verification.
    """
    repo = tmp_path / "textutils"
    build_textutils_repo(repo)
    return repo


@pytest.mark.local_engine
def test_e2e_real_local_model_realistic_bugfix(textutils_repo: Path, tmp_path: Path):
    """More realistic than 10.10's tests: diagnose-and-fix-without-regressing against an existing module
    (not a `TODO` stub), gated on both `pytest` AND `ruff check` — matching how this project's own
    AGENTS.md/CLAUDE.md SDLC actually verifies changes. Run by hand with `pytest -m local_engine`."""
    available, engine_name = _local_engine_available()
    if not available:
        pytest.skip("No local inference engine (Ollama/Prism) reachable on localhost.")

    baseline = subprocess.run(
        [sys.executable, "-m", "pytest", "test_text_utils.py"], cwd=textutils_repo, capture_output=True, text=True
    )
    assert baseline.returncode != 0  # sanity: the fixture's bug actually fails tests before any fix

    storage = tmp_path / ".factory"
    engine = DurableEngine(storage_dir=storage)
    spec = TaskSpec(
        repo_path=str(textutils_repo),
        task_prompt=(
            "test_slugify_collapses_repeated_whitespace in test_text_utils.py is failing against "
            "text_utils.py's slugify() function. Fix the bug so all tests pass. Do not change the "
            "function signature."
        ),
        verification_steps=[
            VerificationStep(id="pytest", argv=[sys.executable, "-m", "pytest", "test_text_utils.py"]),
            VerificationStep(id="ruff", argv=[sys.executable, "-m", "ruff", "check", "text_utils.py"]),
        ],
        # Explicit, not auto-detected: the ruff gate's own argv names text_utils.py as its lint target,
        # and detect_default_gate_paths() can't tell "lint target" apart from "test/gate file" — left to
        # the default it would protect (and silently revert) the very file the model must edit. Only the
        # test file actually needs baseline protection here.
        protected_paths=["test_text_utils.py"],
        max_healing_attempts=5,
        timeout_minutes=5,
    )

    manifest = engine.execute_run(spec=spec, harness=LocalCoderHarness(), run_id="run-e2e-real-model-bugfix")

    assert manifest.status == RunStatus.AWAITING_REVIEW, (
        f"Real model failed the realistic bugfix task after {manifest.healing_attempts} healing "
        f"attempt(s): {manifest.operator_notes}"
    )
    assert manifest.model_telemetry is not None
    assert manifest.model_telemetry.engine == engine_name

    approved = engine.review_run(
        run_id="run-e2e-real-model-bugfix", approve=True, target_branch="feature/real-model-slugify-fix"
    )
    assert approved.status == RunStatus.APPROVED

    after = subprocess.run(
        [sys.executable, "-m", "pytest", "test_text_utils.py"], cwd=textutils_repo, capture_output=True, text=True
    )
    assert after.returncode == 0, after.stdout + after.stderr
    lint = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "text_utils.py"], cwd=textutils_repo, capture_output=True, text=True
    )
    assert lint.returncode == 0, lint.stdout + lint.stderr


def _make_stub_ollama_handler(fixed_code: str) -> type[http.server.BaseHTTPRequestHandler]:
    """A minimal stand-in for Ollama's `/api/generate`, so the CLI e2e test below doesn't depend on a
    real local model (and can't collide with a real Ollama on the developer's machine, since it binds to
    an ephemeral port that is passed to the CLI explicitly via --ollama-url)."""
    body = json.dumps(
        {
            "response": f"```file:primes.py\n{fixed_code}\n```",
            "prompt_eval_count": 42,
            "eval_count": 42,
        }
    ).encode("utf-8")

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"models": []}')

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args) -> None:  # silence request logging
            pass

    return Handler


def test_e2e_cli_run_and_review_round_trip(target_repo: Path, tmp_path: Path):
    """Drives the real `dark-factory` console entrypoint as a subprocess (run, then review --approve),
    proving the operator-facing CLI works end-to-end, not just the `DurableEngine` library API."""
    dark_factory_bin = Path(sys.executable).parent / "dark-factory"
    assert dark_factory_bin.exists(), f"console script not found next to interpreter: {dark_factory_bin}"

    server = http.server.HTTPServer(("127.0.0.1", 0), _make_stub_ollama_handler(_FIXED_PRIMES))
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        storage = tmp_path / ".factory"
        run_result = subprocess.run(
            [
                str(dark_factory_bin),
                "run",
                "--repo",
                str(target_repo),
                "--task",
                "Implement correct is_prime logic in primes.py",
                "--test-cmd",
                f"{sys.executable} -m pytest test_primes.py",
                "--storage-dir",
                str(storage),
                "--ollama-url",
                f"http://127.0.0.1:{port}",
                "--model",
                "stub-model",
            ],
            cwd=target_repo,
            capture_output=True,
            text=True,
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert run_result.returncode == 0, run_result.stdout + run_result.stderr
    assert "AWAITING_REVIEW" in run_result.stdout

    run_id = next(
        line.split(":", 1)[1].strip()
        for line in run_result.stdout.splitlines()
        if line.strip().startswith("🏁 RUN FINISHED")
    )

    review_result = subprocess.run(
        [
            str(dark_factory_bin),
            "review",
            run_id,
            "--approve",
            "--branch",
            "feature/cli-primes",
            "--storage-dir",
            str(storage),
        ],
        cwd=target_repo,
        capture_output=True,
        text=True,
    )
    assert review_result.returncode == 0, review_result.stdout + review_result.stderr
    assert "APPROVED" in review_result.stdout

    after = subprocess.run(
        [sys.executable, "-m", "pytest", "test_primes.py"], cwd=target_repo, capture_output=True, text=True
    )
    assert after.returncode == 0


@pytest.mark.local_engine
def test_e2e_cli_run_and_review_real_ollama(target_repo: Path, tmp_path: Path):
    """Extends `test_e2e_cli_run_and_review_round_trip`: that test only proves the CLI wiring works against
    a stub HTTP server. This drives the real `dark-factory` console script against the operator's actual
    Ollama — no `--ollama-url` override, no stub — so argument parsing, `LocalCoderHarness` construction,
    and stdout formatting are all exercised with a real model, not just via `DurableEngine` directly
    (10.10/10.12) or a stubbed HTTP layer (10.8). Run by hand with `pytest -m local_engine`."""
    available, _ = _local_engine_available()
    if not available:
        pytest.skip("No local inference engine (Ollama/Prism) reachable on localhost.")

    dark_factory_bin = Path(sys.executable).parent / "dark-factory"
    assert dark_factory_bin.exists(), f"console script not found next to interpreter: {dark_factory_bin}"

    storage = tmp_path / ".factory"
    run_result = subprocess.run(
        [
            str(dark_factory_bin),
            "run",
            "--repo",
            str(target_repo),
            "--task",
            "Implement correct is_prime logic in primes.py",
            "--test-cmd",
            f"{sys.executable} -m pytest test_primes.py",
            "--storage-dir",
            str(storage),
        ],
        cwd=target_repo,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert run_result.returncode == 0, run_result.stdout + run_result.stderr
    assert "AWAITING_REVIEW" in run_result.stdout
    assert "Cloud Cost:   $0.00" in run_result.stdout

    run_id = next(
        line.split(":", 1)[1].strip()
        for line in run_result.stdout.splitlines()
        if line.strip().startswith("🏁 RUN FINISHED")
    )

    review_result = subprocess.run(
        [
            str(dark_factory_bin),
            "review",
            run_id,
            "--approve",
            "--branch",
            "feature/cli-real-ollama-primes",
            "--storage-dir",
            str(storage),
        ],
        cwd=target_repo,
        capture_output=True,
        text=True,
    )
    assert review_result.returncode == 0, review_result.stdout + review_result.stderr
    assert "APPROVED" in review_result.stdout

    after = subprocess.run(
        [sys.executable, "-m", "pytest", "test_primes.py"], cwd=target_repo, capture_output=True, text=True
    )
    assert after.returncode == 0, after.stdout + after.stderr


@pytest.fixture
def csvparse_repo(tmp_path: Path) -> Path:
    """A from-scratch parsing task genuinely harder than 10.10/10.12's (which were solved first-try):
    quoted-CSV-field parsing has two edge cases (commas inside quotes, doubled-quote escaping) that a
    naive `str.split(',')` gets completely wrong. Empirically exercised against qwen2.5-coder:14b across 7
    manual runs: 6/7 converged at exactly `healing_attempts == 1` (a genuine second real attempt, each
    landing on a correct state-machine parser); 1/7 exhausted all 5 attempts and ended `FAILED`. That ~85%
    convergence rate is real model variance, not a test bug — kept as-is (rather than simplified further)
    because it's an honest, useful data point about self-healing reliability on a task that actually
    requires reasoning, and this test is `local_engine`-gated (run by hand, not a CI gate) precisely
    because real-model runs are exploratory, not deterministic. If it fails, re-running is expected to
    usually succeed; a *repeated* failure would be worth investigating as a real regression.

    Forensic analysis of that one `FAILED` run (Phase 10.14) found its exact root cause: the model
    reproduced the identical conceptual bug (a backward-look escaped-quote check that's dead code) on all
    6 attempts, verbatim-identical pytest failure every time, while a successful run's first retry used a
    structurally different, correct strategy (forward lookahead) immediately. `SelfHealingLoop` now detects
    a repeated identical verification failure and nudges the repair prompt to try a different approach —
    this should reduce, but is not guaranteed to eliminate, that failure mode; 3 additional post-fix runs
    all converged on the first retry (none exercised the new nudge, since the rare stuck case didn't recur
    in that small sample), so the fix's real-world effect on the failure rate is not yet independently
    re-measured — don't overclaim it "solves" this, same standard 10.12/10.13 already set."""
    repo = tmp_path / "csvparse"
    build_csvparse_repo(repo)
    return repo


@pytest.mark.local_engine
def test_e2e_real_local_model_multi_iteration_healing(csvparse_repo: Path, tmp_path: Path):
    """Extends 10.10/10.12, whose real-model tasks were all solved first try (0 healing attempts) — this
    exercises the actual repair-prompt feedback loop against a real model. Run by hand with
    `pytest -m local_engine`."""
    available, engine_name = _local_engine_available()
    if not available:
        pytest.skip("No local inference engine (Ollama/Prism) reachable on localhost.")

    storage = tmp_path / ".factory"
    engine = DurableEngine(storage_dir=storage)
    spec = TaskSpec(
        repo_path=str(csvparse_repo),
        task_prompt=(
            "Implement parse_csv_line in csvparse.py so that test_csvparse.py passes. It must correctly "
            "handle double-quoted fields that contain commas, and a doubled quote '\"\"' inside a quoted "
            "field represents a single literal quote character."
        ),
        verification_steps=[
            VerificationStep(id="pytest", argv=[sys.executable, "-m", "pytest", "test_csvparse.py"]),
        ],
        max_healing_attempts=5,
        timeout_minutes=5,
    )

    manifest = engine.execute_run(spec=spec, harness=LocalCoderHarness(), run_id="run-e2e-real-model-healing")

    assert manifest.status == RunStatus.AWAITING_REVIEW, (
        f"Real model failed the CSV-parsing task after {manifest.healing_attempts} healing attempt(s): "
        f"{manifest.operator_notes}"
    )
    # The point of this test: it must have actually needed the repair loop, not solved it on attempt 1.
    assert manifest.healing_attempts >= 1
    assert manifest.model_telemetry is not None
    assert manifest.model_telemetry.engine == engine_name

    approved = engine.review_run(
        run_id="run-e2e-real-model-healing", approve=True, target_branch="feature/real-model-csv-parser"
    )
    assert approved.status == RunStatus.APPROVED

    after = subprocess.run(
        [sys.executable, "-m", "pytest", "test_csvparse.py"], cwd=csvparse_repo, capture_output=True, text=True
    )
    assert after.returncode == 0, after.stdout + after.stderr
