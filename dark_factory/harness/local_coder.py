"""LocalCoder harness implementing zero-cloud-token code generation."""

from __future__ import annotations

import math
import re
import time

import requests

from dark_factory.domain.errors import LocalEngineOfflineError, PromptTooLargeError
from dark_factory.domain.types import ModelTelemetry
from dark_factory.harness.base import AgentHarness, HarnessResult
from dark_factory.sandbox.base import Sandbox

_FILE_OPEN_RE = re.compile(r"^(`{3,})file:(.*)$")
_FENCE_RE = re.compile(r"^ {0,3}(`{3,})(.*)$")


MIN_NUM_CTX = 4096
OUTPUT_RESERVE_MIN = 1024  # tokens kept free for the reply when the caller names no larger reserve
_TRUNCATION_MARGIN = 16
# Measured on Ollama 0.34 (plan.md 10.15): a prompt larger than num_ctx is cut to about half the window
# (prompt_eval_count 2050 of 4096), so that count is the truncation signature; a count that fills the window is too.
_HALF_WINDOW_SLACK = 4


def looks_truncated(prompt_tokens: int, num_ctx: int) -> bool:
    """Heuristic: did the engine drop part of the prompt? Based on the reported `prompt_eval_count`."""
    if prompt_tokens >= num_ctx - _TRUNCATION_MARGIN:
        return True
    return abs(prompt_tokens - (num_ctx // 2 + 2)) <= _HALF_WINDOW_SLACK


def estimate_tokens(text: str) -> int:
    """Deliberately pessimistic token estimate (about 3 characters per token)."""
    return math.ceil(len(text) / 3)


class LocalCoderHarness(AgentHarness):
    """Harness that leverages local LLM engines (Ollama, Prism CUDA)."""

    def __init__(
        self,
        model: str = "qwen2.5-coder:14b",
        ollama_url: str = "http://localhost:11434",
        prism_url: str = "http://127.0.0.1:5272/v1",
        timeout: int = 600,
        max_num_ctx: int = 8192,
    ) -> None:
        self.model = model
        self.ollama_url = ollama_url.rstrip("/")
        self.prism_url = prism_url.rstrip("/")
        self.timeout = timeout
        self.max_num_ctx = max_num_ctx

    def check_health(self) -> dict[str, bool]:
        """Check availability of local engines."""
        status = {"ollama": False, "prism": False}
        try:
            r = requests.get(f"{self.ollama_url}/api/tags", timeout=2.0)
            status["ollama"] = r.status_code == 200
        except Exception:
            pass

        try:
            r = requests.get(f"{self.prism_url}/models", timeout=2.0)
            status["prism"] = r.status_code == 200
        except Exception:
            pass

        return status

    def execute_task(
        self,
        sandbox: Sandbox,
        task_prompt: str,
        target_files: list[str] | None = None,
    ) -> HarnessResult:
        """Execute a coding task inside the sandbox using the local model."""
        context_text = self._build_context(sandbox, task_prompt, target_files)
        system_prompt = (
            "You are an expert autonomous software engineer working in the Sovereign Dark Factory.\n"
            "Your changes will be verified by deterministic automated build and test gates.\n"
            "Respond ONLY with the code modifications required to accomplish the task.\n\n"
            "FORMAT RULES:\n"
            "For every file you want to create or update, use this EXACT markdown code fence:\n"
            "```file:path/to/file.ext\n"
            "<complete file contents here>\n"
            "```\n"
            "Do not output truncated code or comments like '// keep rest unchanged'. "
            "Output the full file contents so it can be written directly to disk."
        )

        user_prompt = f"TASK:\n{task_prompt}\n\n{context_text}"

        # The model re-emits whole files, so reserve at least as many output tokens as the context holds.
        reserve = max(OUTPUT_RESERVE_MIN, estimate_tokens(context_text))
        try:
            self._plan_window(system_prompt, user_prompt, reserve)
        except PromptTooLargeError as exc:
            return HarnessResult(
                success=False,
                error=f"{exc} Shorten the task or narrow the context with --target-file PATH (repeatable).",
            )

        # Dispatch generation
        response_text, telemetry = self._call_model(system_prompt, user_prompt, output_reserve=reserve)

        # Parse file blocks
        files_to_write = self._parse_file_blocks(response_text)
        if not files_to_write and target_files and len(target_files) == 1:
            # Fallback: if model wrapped single file in standard ```python ... ``` block
            code = self._extract_generic_code_block(response_text)
            if code:
                files_to_write.append((target_files[0], code))

        if not files_to_write:
            error = "Model did not output any recognizable file code blocks (expected ```file:<path>)."
            if telemetry.num_ctx is not None and looks_truncated(telemetry.prompt_tokens, telemetry.num_ctx):
                # Only explains a failure: a coincidental count must never discard a valid reply.
                error += (
                    f" The prompt was probably truncated by the engine: it processed {telemetry.prompt_tokens} "
                    f"tokens in a {telemetry.num_ctx}-token window, so part of the prompt (including the format "
                    "rules) may have been dropped. Narrow the context with --target-file."
                )
            return HarnessResult(success=False, telemetry=telemetry, raw_response=response_text, error=error)

        modified = []
        for rel_path, content in files_to_write:
            sandbox.write_file(rel_path, content.encode("utf-8"))
            modified.append(rel_path)

        return HarnessResult(
            success=True,
            modified_files=modified,
            telemetry=telemetry,
            raw_response=response_text,
        )

    def _build_context(self, sandbox: Sandbox, task_prompt: str, target_files: list[str] | None) -> str:
        explicit = list(target_files or [])
        files_to_load = list(explicit)
        if not explicit:
            # Fallback: scan the prompt for file paths that exist in the sandbox
            for candidate in re.findall(r"[\w/\.-]+\.[a-zA-Z0-9]+", task_prompt):
                candidate_clean = candidate.strip("`'\",:;()[]")
                try:
                    sandbox.read_file(candidate_clean)
                    if candidate_clean not in files_to_load:
                        files_to_load.append(candidate_clean)
                except Exception:
                    pass

        if not files_to_load:
            return "CONTEXT: Repository root.\n"

        budget = self.max_num_ctx // 2  # applies to auto-detected files only
        context_parts = ["CONTEXT FILES:"]
        for path in files_to_load:
            try:
                content = sandbox.read_file(path).decode("utf-8", errors="replace")
            except Exception as e:
                context_parts.append(f"--- File: {path} (new or unreadable: {e}) ---\n")
                continue
            if not explicit:
                cost = estimate_tokens(content)
                if cost > budget:
                    lines = len(content.splitlines())
                    context_parts.append(
                        f"--- File: {path} ({lines} lines, not inlined: over the auto-detected context budget; "
                        "pass --target-file to include it) ---\n"
                    )
                    continue
                budget -= cost
            context_parts.append(f"--- File: {path} ---\n{content}\n")
        return "\n".join(context_parts)

    def _plan_window(self, system_prompt: str, user_prompt: str, output_reserve: int) -> int:
        """Return the `num_ctx` to request, or raise PromptTooLargeError before any model call."""
        needed = estimate_tokens(system_prompt) + estimate_tokens(user_prompt) + output_reserve
        if needed > self.max_num_ctx:
            raise PromptTooLargeError(
                f"Prompt needs about {needed} tokens (prompt plus {output_reserve} reserved for the reply) "
                f"but max_num_ctx is {self.max_num_ctx}."
            )
        return min(self.max_num_ctx, max(MIN_NUM_CTX, needed))

    def _call_model(
        self, system_prompt: str, user_prompt: str, output_reserve: int = OUTPUT_RESERVE_MIN
    ) -> tuple[str, ModelTelemetry]:
        """Call Ollama native API or OpenAI-compatible endpoint."""
        num_ctx = self._plan_window(system_prompt, user_prompt, output_reserve)
        start_time = time.monotonic()

        ollama_err = ""
        # Try Ollama first
        try:
            payload = {
                "model": self.model,
                "system": system_prompt,
                "prompt": user_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "num_ctx": num_ctx,
                },
            }
            resp = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                duration = time.monotonic() - start_time
                prompt_tokens = data.get("prompt_eval_count", 0)
                completion_tokens = data.get("eval_count", 0)
                total_tokens = prompt_tokens + completion_tokens
                tps = completion_tokens / duration if duration > 0 else 0.0

                telemetry = ModelTelemetry(
                    engine="ollama",
                    model_name=self.model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    duration_sec=round(duration, 3),
                    tokens_per_sec=round(tps, 2),
                    cost_usd=0.0,
                    num_ctx=num_ctx,
                )
                return data.get("response", ""), telemetry
            elif resp.status_code == 404:
                ollama_err = f"Model '{self.model}' not found in Ollama (HTTP 404). Run 'ollama pull {self.model}'."
            else:
                ollama_err = f"Ollama HTTP {resp.status_code}: {resp.text}"
        except requests.RequestException as e:
            ollama_err = f"Ollama connection error: {e}"

        # Fallback to Prism / OpenAI-compatible endpoint
        prism_err = ""
        try:
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
            }
            resp = requests.post(
                f"{self.prism_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                duration = time.monotonic() - start_time
                usage = data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
                tps = completion_tokens / duration if duration > 0 else 0.0

                text = data["choices"][0]["message"]["content"]
                telemetry = ModelTelemetry(
                    engine="prism",
                    model_name=self.model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    duration_sec=round(duration, 3),
                    tokens_per_sec=round(tps, 2),
                    cost_usd=0.0,
                )
                return text, telemetry
            else:
                prism_err = f"Prism HTTP {resp.status_code}: {resp.text}"
        except requests.RequestException as e:
            prism_err = f"Prism connection error: {e}"

        raise LocalEngineOfflineError(
            f"All local inference engines failed.\n"
            f" - Ollama ({self.ollama_url}): {ollama_err or 'No response'}\n"
            f" - Prism ({self.prism_url}): {prism_err or 'No response'}"
        )

    def _parse_file_blocks(self, text: str) -> list[tuple[str, str]]:
        """Parse ```file:path/to/file blocks from model response.

        The scan is line-based so file contents may contain their own markdown fences: a fence with an
        info string (```python) opens a nested block, a bare fence closes it, and only a bare fence at
        nesting depth 0 (and at least as long as the opening one) terminates the file block. A block that
        is never terminated (truncated response) is discarded rather than written half-complete.
        """
        result: list[tuple[str, str]] = []
        current_path: str | None = None
        outer_len = 0
        depth = 0
        buffer: list[str] = []

        for line in text.splitlines(keepends=True):
            stripped = line.rstrip("\r\n")
            if current_path is None:
                opener = _FILE_OPEN_RE.match(stripped)
                if opener and opener.group(2).strip():
                    current_path = opener.group(2).strip()
                    outer_len = len(opener.group(1))
                    depth = 0
                    buffer = []
                continue

            fence = _FENCE_RE.match(stripped)
            if fence:
                fence_len, info = len(fence.group(1)), fence.group(2).strip()
                if info:
                    depth += 1
                elif depth > 0:
                    depth -= 1
                elif fence_len >= outer_len:
                    result.append((current_path, "".join(buffer)))
                    current_path = None
                    continue
            buffer.append(line)

        return result

    def _extract_generic_code_block(self, text: str) -> str | None:
        """Extract code from a standard markdown block ```python ... ```."""
        match = re.search(r"```(?:[a-zA-Z0-9_\-]+)?[\r\n]([\s\S]*?)```", text)
        if match:
            return match.group(1).strip()
        return None
