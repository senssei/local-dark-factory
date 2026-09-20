"""LocalCoder harness implementing zero-cloud-token code generation."""

from __future__ import annotations

import re
import time

import requests

from dark_factory.domain.errors import LocalEngineOfflineError
from dark_factory.domain.types import ModelTelemetry
from dark_factory.harness.base import AgentHarness, HarnessResult
from dark_factory.sandbox.base import Sandbox


class LocalCoderHarness(AgentHarness):
    """Harness that leverages local LLM engines (Ollama, Prism CUDA, Foundry)."""

    def __init__(
        self,
        model: str = "qwen2.5-coder:14b",
        ollama_url: str = "http://localhost:11434",
        prism_url: str = "http://127.0.0.1:5272/v1",
        timeout: int = 600,
    ) -> None:
        self.model = model
        self.ollama_url = ollama_url.rstrip("/")
        self.prism_url = prism_url.rstrip("/")
        self.timeout = timeout

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

        # Dispatch generation
        response_text, telemetry = self._call_model(system_prompt, user_prompt)

        # Parse file blocks
        files_to_write = self._parse_file_blocks(response_text)
        if not files_to_write and target_files and len(target_files) == 1:
            # Fallback: if model wrapped single file in standard ```python ... ``` block
            code = self._extract_generic_code_block(response_text)
            if code:
                files_to_write.append((target_files[0], code))

        if not files_to_write:
            return HarnessResult(
                success=False,
                telemetry=telemetry,
                raw_response=response_text,
                error="Model did not output any recognizable file code blocks (expected ```file:<path>).",
            )

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
        files_to_load = list(target_files or [])
        if not files_to_load:
            # Scan prompt for potential file paths that exist in sandbox
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

        context_parts = ["CONTEXT FILES:"]
        for path in files_to_load:
            try:
                content = sandbox.read_file(path).decode("utf-8", errors="replace")
                context_parts.append(f"--- File: {path} ---\n{content}\n")
            except Exception as e:
                context_parts.append(f"--- File: {path} (new or unreadable: {e}) ---\n")
        return "\n".join(context_parts)

    def _call_model(self, system_prompt: str, user_prompt: str) -> tuple[str, ModelTelemetry]:
        """Call Ollama native API or OpenAI-compatible endpoint."""
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
        """Parse ```file:path/to/file blocks from model response."""
        pattern = re.compile(r"```file:([^\n\r]+)[\r\n]([\s\S]*?)```")
        matches = pattern.findall(text)
        result = []
        for path_str, content in matches:
            clean_path = path_str.strip()
            result.append((clean_path, content))
        return result

    def _extract_generic_code_block(self, text: str) -> str | None:
        """Extract code from a standard markdown block ```python ... ```."""
        match = re.search(r"```(?:[a-zA-Z0-9_\-]+)?[\r\n]([\s\S]*?)```", text)
        if match:
            return match.group(1).strip()
        return None
