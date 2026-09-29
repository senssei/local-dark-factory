"""Integration tests for the dashboard's HTTP server — real requests over a real ephemeral local socket."""

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from dark_factory.dashboard.server import _make_handler
from dark_factory.domain.types import EvidenceManifest, RunStatus
from dark_factory.eval.runner import EvalReport, EvalRunResult, save_report
from dark_factory.storage import EvidenceLocker


@pytest.fixture
def dashboard_server(tmp_path: Path):
    storage_dir = tmp_path / ".factory"
    locker = EvidenceLocker(storage_dir=storage_dir)
    manifest = EvidenceManifest.create(
        run_id="run-dash-1", repo_path="/tmp/repo", base_rev="abc123", status=RunStatus.AWAITING_REVIEW
    )
    locker.save_run(manifest, patch_content="diff --git a/x b/x\n+hi\n", transcript="ok")

    report = EvalReport(
        started_at="2026-09-29T00:00:00Z",
        finished_at="2026-09-29T00:01:00Z",
        model="qwen2.5-coder:14b",
        ollama_url="http://localhost:11434",
        prism_url="http://127.0.0.1:5272/v1",
        results=[
            EvalRunResult(
                scenario="primes",
                run_id="eval-primes-1",
                converged=True,
                status="AWAITING_REVIEW",
                healing_attempts=0,
                repeated_failure_streak_fired=False,
                duration_sec=1.0,
            )
        ],
    )
    save_report(report, storage_dir)

    handler = _make_handler(storage_dir)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _get(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def test_dashboard_root_lists_runs(dashboard_server: str):
    status, body = _get(dashboard_server + "/")
    assert status == 200
    assert "run-dash-1" in body


def test_dashboard_run_detail(dashboard_server: str):
    status, body = _get(dashboard_server + "/runs/run-dash-1")
    assert status == 200
    assert "AWAITING_REVIEW" in body
    assert "diff --git a/x b/x" in body


def test_dashboard_run_detail_not_found(dashboard_server: str):
    status, _ = _get(dashboard_server + "/runs/does-not-exist")
    assert status == 404


def test_dashboard_eval_view(dashboard_server: str):
    status, body = _get(dashboard_server + "/eval")
    assert status == 200
    assert "primes" in body


def test_dashboard_unknown_path_404(dashboard_server: str):
    status, _ = _get(dashboard_server + "/nope")
    assert status == 404


def test_dashboard_api_runs(dashboard_server: str):
    status, body = _get(dashboard_server + "/api/runs")
    assert status == 200
    data = json.loads(body)
    assert data[0]["run_id"] == "run-dash-1"


def test_dashboard_api_eval(dashboard_server: str):
    status, body = _get(dashboard_server + "/api/eval")
    assert status == 200
    data = json.loads(body)
    assert data[0]["results"][0]["scenario"] == "primes"


def test_dashboard_rejects_non_get_methods(dashboard_server: str):
    for method in ("POST", "PUT", "DELETE", "PATCH"):
        req = urllib.request.Request(dashboard_server + "/", method=method)
        try:
            urllib.request.urlopen(req, timeout=5)
            raise AssertionError(f"{method} unexpectedly succeeded")
        except urllib.error.HTTPError as e:
            assert e.code == 405
