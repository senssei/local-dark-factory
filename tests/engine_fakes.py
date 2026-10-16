"""Fake Ollama and Prism HTTP engines that track which model each one has been asked to load.

They mimic only what the harness and the residency checks touch: Ollama `POST /api/generate` and `GET /api/ps`,
Prism `POST /chat/completions` and `GET /status` (the real `/v1/status`). A model counts as loaded on an engine once
that engine received a request for it. No real inference, no network beyond localhost.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

_FIXED_PRIMES = (
    "def is_prime(n: int) -> bool:\n"
    "    if n < 2:\n"
    "        return False\n"
    "    for i in range(2, int(n**0.5) + 1):\n"
    "        if n % i == 0:\n"
    "            return False\n"
    "    return True\n"
)


def _reply_text(system_prompt: str) -> str:
    """A coder prompt (it carries the file-block format rules) gets a fix for `primes.py`; anything else gets JSON."""
    if "```file:" in system_prompt:
        return f"```file:primes.py\n{_FIXED_PRIMES}```"
    return json.dumps({"summary": "s", "findings": []})


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:  # keep test output quiet
        pass

    def _send(self, payload: dict, code: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        engine: FakeEngine = self.server.engine  # type: ignore[attr-defined]
        if self.path == engine.status_path:
            self._send(engine.status_payload())
        elif self.path == engine.models_path:
            self._send({"models": [], "data": []})
        else:
            self._send({}, 404)

    def do_POST(self) -> None:
        engine: FakeEngine = self.server.engine  # type: ignore[attr-defined]
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
        if self.path != engine.generate_path:
            self._send({}, 404)
            return
        engine.record(body.get("model", ""))
        self._send(engine.reply(body))


class FakeEngine:
    generate_path = ""
    status_path = ""
    models_path = ""

    def __init__(self) -> None:
        self.requested: list[str] = []
        self.loaded: list[str] = []
        self._lock = threading.Lock()
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._server.engine = self  # type: ignore[attr-defined]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    def record(self, model: str) -> None:
        with self._lock:
            self.requested.append(model)
            if model not in self.loaded:
                self.loaded.append(model)

    def __enter__(self) -> FakeEngine:
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def status_payload(self) -> dict:
        raise NotImplementedError

    def reply(self, body: dict) -> dict:
        raise NotImplementedError


class FakePrism(FakeEngine):
    generate_path = "/chat/completions"
    status_path = "/status"
    models_path = "/models"

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def status_payload(self) -> dict:
        with self._lock:
            return {"status": "ok", "active_model": self.loaded[-1] if self.loaded else None}

    def reply(self, body: dict) -> dict:
        system = body["messages"][0]["content"]
        return {
            "choices": [{"message": {"content": _reply_text(system)}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        }


class FakeOllama(FakeEngine):
    generate_path = "/api/generate"
    status_path = "/api/ps"
    models_path = "/api/tags"

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def status_payload(self) -> dict:
        with self._lock:
            return {"models": [{"name": m} for m in self.loaded]}

    def reply(self, body: dict) -> dict:
        return {"response": _reply_text(body.get("system", "")), "prompt_eval_count": 10, "eval_count": 10}


def loaded_models(ollama_url: str, prism_url: str) -> dict[str, set[str]]:
    """Models resident per engine, read from Ollama `/api/ps` and Prism `/status`. An unreachable engine reports none."""
    resident: dict[str, set[str]] = {"ollama": set(), "prism": set()}
    try:
        data = requests.get(f"{ollama_url.rstrip('/')}/api/ps", timeout=2).json()
        resident["ollama"] = {m["name"] for m in data.get("models", [])}
    except (requests.RequestException, ValueError):
        pass
    try:
        active = requests.get(f"{prism_url.rstrip('/')}/status", timeout=2).json().get("active_model")
        resident["prism"] = {active} if active else set()
    except (requests.RequestException, ValueError):
        pass
    return resident
