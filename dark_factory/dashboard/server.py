"""Local, read-only HTTP server for the dashboard.

Stdlib-only (`http.server`) — no new runtime dependency, consistent with the project's single existing
dependency (`requests`). Every non-`GET` request gets `405`: this is the literal, testable enforcement of
the dashboard's read-only guarantee. Binds to `127.0.0.1` only — there is no host/bind-address flag.
"""

from __future__ import annotations

import json
import webbrowser
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from dark_factory.dashboard.views import render_eval_view, render_layout, render_run_detail, render_runs_list
from dark_factory.domain.errors import RunNotFoundError
from dark_factory.eval.runner import list_eval_reports, load_report
from dark_factory.storage import EvidenceLocker


def _make_handler(storage_dir: Path) -> type[BaseHTTPRequestHandler]:
    # A plain EvidenceLocker (disk-only), not a DurableEngine: the dashboard is read-only and must work
    # purely off the evidence already on disk, without opening (or requiring) a SQLite connection.
    locker = EvidenceLocker(storage_dir=storage_dir)

    def _load_eval_reports() -> list:
        return [load_report(p) for p in list_eval_reports(storage_dir)]

    class DashboardRequestHandler(BaseHTTPRequestHandler):
        server_version = "DarkFactoryDashboard/1.0"

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            try:
                if path == "/":
                    self._send_html(render_layout("Runs", render_runs_list(locker.list_runs())))
                elif path.startswith("/runs/") and len(path) > len("/runs/"):
                    self._render_run(path.removeprefix("/runs/"))
                elif path == "/eval":
                    self._send_html(render_layout("Eval", render_eval_view(_load_eval_reports())))
                elif path == "/api/runs":
                    self._send_json([asdict(r) for r in locker.list_runs()])
                elif path == "/api/eval":
                    self._send_json([asdict(r) for r in _load_eval_reports()])
                else:
                    self._send_text(404, "Not Found")
            except Exception as e:
                self._send_text(500, f"Internal error: {e}")

        def _render_run(self, run_id: str) -> None:
            try:
                manifest = locker.load_manifest(run_id)
                patch = locker.load_patch(run_id)
            except RunNotFoundError:
                self._send_text(404, f"Run not found: {run_id}")
                return
            self._send_html(render_layout(f"Run {run_id}", render_run_detail(manifest, patch)))

        def _reject_write(self) -> None:
            self._send_text(405, "Method Not Allowed: this dashboard is read-only")

        do_POST = _reject_write
        do_PUT = _reject_write
        do_DELETE = _reject_write
        do_PATCH = _reject_write

        def _send_html(self, body: str) -> None:
            self._send_bytes(200, "text/html; charset=utf-8", body.encode("utf-8"))

        def _send_json(self, data) -> None:
            self._send_bytes(200, "application/json", json.dumps(data, default=str).encode("utf-8"))

        def _send_text(self, code: int, message: str) -> None:
            self._send_bytes(code, "text/plain; charset=utf-8", message.encode("utf-8"))

        def _send_bytes(self, code: int, content_type: str, body: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:  # silence default stderr access logging
            pass

    return DashboardRequestHandler


def run_dashboard(storage_dir: Path, port: int = 8420, open_browser: bool = True) -> None:
    """Serve the read-only dashboard on `127.0.0.1:<port>` until interrupted (Ctrl-C)."""
    handler = _make_handler(Path(storage_dir))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"Dark Factory Dashboard: {url}")
    print("Read-only — no run/review actions are available here. Press Ctrl-C to stop.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
