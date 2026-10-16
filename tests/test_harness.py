"""Unit tests for LocalCoderHarness."""

from unittest.mock import patch

import pytest

from dark_factory.domain.errors import LocalEngineOfflineError
from dark_factory.domain.types import ModelTelemetry
from dark_factory.harness import LocalCoderHarness
from dark_factory.sandbox.base import Sandbox


class MockSandbox(Sandbox):
    def __init__(self):
        self.files = {}

    def create(self, base_rev: str = "HEAD") -> None:
        pass

    def execute(self, argv, cwd=None, env=None, timeout=300, step_id="exec"):
        raise NotImplementedError

    def read_file(self, rel_path: str) -> bytes:
        if rel_path in self.files:
            return self.files[rel_path]
        raise FileNotFoundError(rel_path)

    def write_file(self, rel_path: str, content: bytes) -> None:
        self.files[rel_path] = content

    def get_diff(self) -> str:
        return ""

    def restore_paths(self, paths: list[str], rev: str | None = None) -> list[str]:
        return []

    def destroy(self) -> None:
        pass


def test_parse_file_blocks():
    harness = LocalCoderHarness()
    sample_response = """
Here are the changes:

```file:src/math.py
def add(a: int, b: int) -> int:
    return a + b
```

And here is the test:

```file:tests/test_math.py
from src.math import add

def test_add():
    assert add(2, 3) == 5
```
    """
    blocks = harness._parse_file_blocks(sample_response)
    assert len(blocks) == 2
    assert blocks[0][0] == "src/math.py"
    assert "def add(a: int, b: int)" in blocks[0][1]
    assert blocks[1][0] == "tests/test_math.py"
    assert "assert add(2, 3) == 5" in blocks[1][1]


def test_execute_task_mocked():
    harness = LocalCoderHarness()
    sandbox = MockSandbox()

    mock_telemetry = ModelTelemetry(
        engine="ollama",
        model_name="qwen2.5-coder:14b",
        prompt_tokens=50,
        completion_tokens=100,
        total_tokens=150,
        duration_sec=2.5,
        tokens_per_sec=40.0,
        cost_usd=0.0,
    )
    mock_response = "Sure, here is the file:\n```file:calc.py\ndef square(x):\n    return x * x\n```"

    with patch.object(harness, "_call_model", return_value=(mock_response, mock_telemetry)):
        result = harness.execute_task(
            sandbox=sandbox,
            task_prompt="Implement square function in calc.py",
        )

        assert result.success
        assert result.modified_files == ["calc.py"]
        assert b"def square(x):" in sandbox.files["calc.py"]
        assert result.telemetry.cost_usd == 0.0
        assert result.telemetry.tokens_per_sec == 40.0


def test_offline_engine_raises():
    harness = LocalCoderHarness(
        ollama_url="http://127.0.0.1:9999",
        prism_url="http://127.0.0.1:9998/v1",
        timeout=1,
    )
    sandbox = MockSandbox()

    with pytest.raises(LocalEngineOfflineError):
        harness.execute_task(sandbox, "do something")


def test_parse_file_blocks_keeps_inner_code_fences():
    """A README containing its own fenced blocks must not be truncated at the first inner fence."""
    harness = LocalCoderHarness()
    response = (
        "```file:README.md\n"
        "# Title\n"
        "\n"
        "```python\n"
        "print(1)\n"
        "```\n"
        "\n"
        "Trailing paragraph.\n"
        "```\n"
        "\n"
        "```file:calc.py\n"
        "x = 1\n"
        "```\n"
    )
    blocks = harness._parse_file_blocks(response)
    assert [p for p, _ in blocks] == ["README.md", "calc.py"]
    readme = dict(blocks)["README.md"]
    assert readme == "# Title\n\n```python\nprint(1)\n```\n\nTrailing paragraph.\n"
    assert dict(blocks)["calc.py"] == "x = 1\n"


def test_parse_file_blocks_longer_outer_fence():
    harness = LocalCoderHarness()
    response = "````file:doc.md\ntext\n```\nnot a terminator\n```\n````\n"
    assert harness._parse_file_blocks(response) == [("doc.md", "text\n```\nnot a terminator\n```\n")]


def test_parse_file_blocks_drops_unterminated_block():
    """A truncated model response must never produce a half-written file."""
    harness = LocalCoderHarness()
    response = "```file:ok.py\nx = 1\n```\n```file:cut.py\ndef f():\n    retur"
    assert harness._parse_file_blocks(response) == [("ok.py", "x = 1\n")]


def test_parse_file_blocks_handles_crlf():
    harness = LocalCoderHarness()
    blocks = harness._parse_file_blocks("```file:a.py\r\nx = 1\r\n```\r\n")
    assert blocks == [("a.py", "x = 1\r\n")]


def test_parse_file_blocks_allows_up_to_three_leading_spaces():
    """CommonMark code fences may be indented by 0 to 3 spaces (DF-LIVE-08)."""
    harness = LocalCoderHarness()
    # 1 space (as observed from Mistral-7B after [/INST])
    response_1_space = " ```file:primes.py\ndef is_prime(n):\n    return True\n```"
    blocks_1 = harness._parse_file_blocks(response_1_space)
    assert len(blocks_1) == 1
    assert blocks_1[0][0] == "primes.py"
    assert "def is_prime(n):" in blocks_1[0][1]

    # 2 spaces
    response_2_spaces = "  ```file:calc.py\nx = 42\n  ```"
    blocks_2 = harness._parse_file_blocks(response_2_spaces)
    assert len(blocks_2) == 1
    assert blocks_2[0][0] == "calc.py"
    assert blocks_2[0][1] == "x = 42\n"

    # 3 spaces
    response_3_spaces = "   ```file:text.py\ny = 'hello'\n   ```"
    blocks_3 = harness._parse_file_blocks(response_3_spaces)
    assert len(blocks_3) == 1
    assert blocks_3[0][0] == "text.py"
    assert blocks_3[0][1] == "y = 'hello'\n"


def test_parse_file_blocks_rejects_four_or_more_leading_spaces():
    """In CommonMark, 4 or more leading spaces represent an indented code block, not a fenced code block."""
    harness = LocalCoderHarness()
    response_4_spaces = "    ```file:foo.py\nx = 1\n    ```"
    assert harness._parse_file_blocks(response_4_spaces) == []


class _FakeResponse:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status
        self.text = str(data)

    def json(self):
        return self._data


def _ollama_ok(prompt_eval_count=100, text="ok"):
    return _FakeResponse({"response": text, "prompt_eval_count": prompt_eval_count, "eval_count": 10})


def test_estimate_tokens_is_pessimistic_ceil_of_len_over_three():
    from dark_factory.harness.local_coder import estimate_tokens

    assert estimate_tokens("") == 0
    assert estimate_tokens("abc") == 1
    assert estimate_tokens("abcd") == 2


def test_call_model_sends_num_ctx_sized_to_prompt():
    harness = LocalCoderHarness(max_num_ctx=16384)
    big = "x" * 15000  # 5000 tokens estimated
    with patch("dark_factory.harness.local_coder.requests.post", return_value=_ollama_ok(5000)) as post:
        _, telemetry = harness._call_model("sys", big)
    sent = post.call_args.kwargs["json"]["options"]["num_ctx"]
    assert 5000 < sent <= 16384
    assert telemetry.num_ctx == sent


def test_num_ctx_is_clamped_to_ceiling_and_floor():
    harness = LocalCoderHarness(max_num_ctx=8192)
    with patch("dark_factory.harness.local_coder.requests.post", return_value=_ollama_ok()) as post:
        harness._call_model("s", "tiny")
        assert post.call_args.kwargs["json"]["options"]["num_ctx"] == 4096
        harness._call_model("s", "x" * 18000)  # 6000 tokens + reserve lands under the ceiling
        assert post.call_args.kwargs["json"]["options"]["num_ctx"] <= 8192


def test_call_model_fails_before_request_when_prompt_exceeds_ceiling():
    from dark_factory.domain.errors import HarnessError

    harness = LocalCoderHarness(max_num_ctx=4096)
    with patch("dark_factory.harness.local_coder.requests.post") as post:
        with pytest.raises(HarnessError, match="max_num_ctx"):
            harness._call_model("s", "x" * 20000)
    post.assert_not_called()


def test_execute_task_fails_before_model_call_when_prompt_exceeds_ceiling():
    harness = LocalCoderHarness(max_num_ctx=4096)
    sandbox = MockSandbox()
    sandbox.files["big.py"] = b"x = 1\n" * 5000
    with patch("dark_factory.harness.local_coder.requests.post") as post:
        result = harness.execute_task(sandbox, "edit big.py", target_files=["big.py"])
    post.assert_not_called()
    assert not result.success
    assert "--target-file" in result.error and "4096" in result.error


def test_execute_task_explains_a_blockless_reply_as_probable_truncation_at_half_window():
    # Measured on Ollama 0.34: a prompt larger than num_ctx is cut to about half the window (2050 of 4096).
    harness = LocalCoderHarness(max_num_ctx=8192)
    sandbox = MockSandbox()
    with patch("dark_factory.harness.local_coder.requests.post", return_value=_ollama_ok(2050, "I cannot say")):
        result = harness.execute_task(sandbox, "write a.py")
    assert not result.success
    assert "truncat" in result.error.lower() and "4096" in result.error


def test_execute_task_keeps_a_valid_reply_even_when_the_signature_matches():
    # A coincidental count must never discard good output; the gates decide, not the heuristic.
    harness = LocalCoderHarness(max_num_ctx=8192)
    sandbox = MockSandbox()
    reply = "```file:a.py\nx = 1\n```"
    with patch("dark_factory.harness.local_coder.requests.post", return_value=_ollama_ok(2050, reply)):
        assert harness.execute_task(sandbox, "write a.py").success
    assert sandbox.files["a.py"] == b"x = 1\n"


def test_execute_task_reports_truncation_when_prompt_eval_count_fills_the_window():
    harness = LocalCoderHarness(max_num_ctx=8192)
    with patch("dark_factory.harness.local_coder.requests.post", return_value=_ollama_ok(4090, "prose only")):
        assert not harness.execute_task(MockSandbox(), "write a.py").success


def test_execute_task_accepts_prompt_eval_count_that_is_not_a_truncation_signature():
    harness = LocalCoderHarness(max_num_ctx=8192)
    reply = "```file:a.py\nx = 1\n```"
    with patch("dark_factory.harness.local_coder.requests.post", return_value=_ollama_ok(1500, reply)):
        assert harness.execute_task(MockSandbox(), "write a.py").success


def test_telemetry_records_num_ctx_and_old_json_still_loads():
    from dark_factory.domain.types import ModelTelemetry

    assert ModelTelemetry(engine="ollama", model_name="m").num_ctx is None
    assert ModelTelemetry(engine="ollama", model_name="m", num_ctx=8192).num_ctx == 8192
    old = {"engine": "ollama", "model_name": "m", "prompt_tokens": 1}
    assert ModelTelemetry(**old).num_ctx is None


def test_build_context_stubs_auto_detected_file_over_budget():
    harness = LocalCoderHarness(max_num_ctx=8192)  # auto budget = 4096 tokens
    sandbox = MockSandbox()
    sandbox.files["docs/cli.md"] = b"line\n" * 178
    sandbox.files["engine.py"] = b"code = 1\n" * 519 * 4
    ctx = harness._build_context(sandbox, "update docs/cli.md using engine.py", None)
    assert "--- File: docs/cli.md ---" in ctx
    assert "--- File: engine.py (2076 lines, not inlined: over the auto-detected context budget" in ctx
    assert "pass --target-file to include it" in ctx
    assert "code = 1" not in ctx


def test_build_context_small_auto_detected_files_inlined():
    harness = LocalCoderHarness(max_num_ctx=8192)
    sandbox = MockSandbox()
    sandbox.files["a.py"] = b"A = 1\n"
    sandbox.files["b.py"] = b"B = 2\n"
    ctx = harness._build_context(sandbox, "change a.py and b.py", None)
    assert "A = 1" in ctx and "B = 2" in ctx and "not inlined" not in ctx


def test_build_context_explicit_target_files_inlined_in_full_and_disable_detection():
    harness = LocalCoderHarness(max_num_ctx=8192)
    sandbox = MockSandbox()
    sandbox.files["big.py"] = b"x = 1\n" * 5000
    sandbox.files["other.py"] = b"OTHER = 1\n"
    ctx = harness._build_context(sandbox, "edit other.py", ["big.py"])
    assert ctx.count("x = 1") == 5000
    assert "OTHER" not in ctx and "not inlined" not in ctx


def test_plan_window_never_exceeds_a_small_ceiling():
    assert LocalCoderHarness(max_num_ctx=2048)._plan_window("a", "b", 1024) == 2048


def test_with_model_keeps_endpoint_configuration():
    original = LocalCoderHarness(
        model="qwen2.5-coder:14b",
        ollama_url="http://127.0.0.1:1/",
        prism_url="http://127.0.0.1:2/v1",
        timeout=42,
        max_num_ctx=6144,
    )

    derived = original.with_model("Phi-4-mini-instruct-cuda-gpu")

    assert derived is not original
    assert derived.model == "Phi-4-mini-instruct-cuda-gpu"
    assert derived.ollama_url == original.ollama_url
    assert derived.prism_url == original.prism_url
    assert derived.timeout == 42
    assert derived.max_num_ctx == 6144
    assert original.model == "qwen2.5-coder:14b"


def test_with_model_preserves_the_harness_subclass():
    class Recording(LocalCoderHarness):
        extra = "kept"

    derived = Recording(timeout=7).with_model("m")

    assert type(derived) is Recording
    assert derived.timeout == 7


def _prism_ok(content="ok", finish_reason="stop", reasoning=None, completion_tokens=10):
    message = {"content": content}
    if reasoning is not None:
        message["reasoning_content"] = reasoning
    return _FakeResponse(
        {
            "choices": [{"message": message, "finish_reason": finish_reason}],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": completion_tokens,
                "total_tokens": 100 + completion_tokens,
            },
        }
    )


def _prism_only(prism_response):
    """requests.post side effect: Ollama is unreachable, Prism answers `prism_response`."""
    import requests

    def post(url, **kwargs):
        if "/api/generate" in url:
            raise requests.ConnectionError("ollama down")
        return prism_response

    return post


def test_df_live_02_prism_request_carries_the_output_reserve_as_max_tokens():
    harness = LocalCoderHarness(max_num_ctx=16384)
    with patch("dark_factory.harness.local_coder.requests.post", side_effect=_prism_only(_prism_ok())) as post:
        _, telemetry = harness._call_model("sys", "user")
        assert post.call_args.kwargs["json"]["max_tokens"] == 1024
        assert telemetry.max_tokens == 1024
        harness._call_model("sys", "user", output_reserve=2500)
        assert post.call_args.kwargs["json"]["max_tokens"] == 2500


def test_df_live_03_telemetry_keeps_the_prism_finish_reason_and_reasoning_length():
    harness = LocalCoderHarness()
    reply = _prism_ok(content="", finish_reason="length", reasoning="thinking hard", completion_tokens=1024)
    with patch("dark_factory.harness.local_coder.requests.post", side_effect=_prism_only(reply)):
        text, telemetry = harness._call_model("sys", "user")

    assert text == ""
    assert telemetry.finish_reason == "length"
    assert telemetry.reasoning_chars == len("thinking hard")
    assert telemetry.completion_tokens == 1024


def test_df_live_03_telemetry_keeps_the_ollama_done_reason_and_sends_no_num_predict():
    harness = LocalCoderHarness()
    response = _FakeResponse(
        {"response": "x", "prompt_eval_count": 10, "eval_count": 5, "done_reason": "length", "thinking": "abc"}
    )
    with patch("dark_factory.harness.local_coder.requests.post", return_value=response) as post:
        _, telemetry = harness._call_model("sys", "user")

    assert "num_predict" not in post.call_args.kwargs["json"]["options"]
    assert telemetry.finish_reason == "length"
    assert telemetry.reasoning_chars == 3
    assert telemetry.max_tokens is None


def test_df_live_03_missing_finish_reason_stays_unknown():
    harness = LocalCoderHarness()
    with patch("dark_factory.harness.local_coder.requests.post", return_value=_ollama_ok()):
        _, telemetry = harness._call_model("sys", "user")
    assert telemetry.finish_reason is None
    assert telemetry.reasoning_chars == 0


def _telemetry(finish_reason="stop", reasoning_chars=0, completion_tokens=1024, max_tokens=1024):
    return ModelTelemetry(
        engine="prism",
        model_name="m",
        completion_tokens=completion_tokens,
        max_tokens=max_tokens,
        finish_reason=finish_reason,
        reasoning_chars=reasoning_chars,
    )


_TWO_FILES = "```file:a.py\nA = 1\n```\n```file:b.py\nB = 2\n```\n"


def _run_with_reply(text, telemetry):
    harness = LocalCoderHarness()
    sandbox = MockSandbox()
    with patch.object(harness, "_call_model", return_value=(text, telemetry)):
        result = harness.execute_task(sandbox, "task")
    return result, sandbox


def test_df_live_03_length_reply_with_complete_blocks_writes_nothing():
    result, sandbox = _run_with_reply(_TWO_FILES + "```file:c.py\nC =", _telemetry("length"))

    assert not result.success
    assert sandbox.files == {}
    assert "truncated" in result.error.lower()
    assert "1024" in result.error and "--target-file" in result.error
    assert "recognizable" not in result.error
    assert result.raw_response.startswith("```file:a.py")


def test_df_live_03_length_reply_with_a_single_complete_block_also_writes_nothing():
    result, sandbox = _run_with_reply("```file:a.py\nA = 1\n```\n", _telemetry("length"))

    assert not result.success and sandbox.files == {}


def test_df_live_03_stop_reply_with_the_same_blocks_is_applied():
    result, sandbox = _run_with_reply(_TWO_FILES, _telemetry("stop"))

    assert result.success
    assert set(sandbox.files) == {"a.py", "b.py"}


def test_df_live_07_empty_content_with_reasoning_is_reported_and_never_executed():
    result, sandbox = _run_with_reply("", _telemetry("stop", reasoning_chars=900, completion_tokens=110))

    assert not result.success and sandbox.files == {}
    assert "reasoning" in result.error.lower() and "no answer" in result.error.lower()
    assert "truncated" not in result.error.lower()


def test_df_live_07_null_content_with_reasoning_reaches_the_no_answer_error():
    harness = LocalCoderHarness()
    sandbox = MockSandbox()
    reply = _FakeResponse(
        {
            "choices": [
                {
                    "message": {"content": None, "reasoning_content": "```file:evil.py\nX = 1\n```"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        }
    )
    with patch("dark_factory.harness.local_coder.requests.post", side_effect=_prism_only(reply)):
        result = harness.execute_task(sandbox, "task")

    assert not result.success
    assert sandbox.files == {}  # a file block inside the reasoning text is never applied
    assert "no answer" in result.error.lower()
    assert result.raw_response == ""


def test_df_live_07_whitespace_only_content_with_reasoning_is_no_answer():
    result, sandbox = _run_with_reply("  \n", _telemetry("stop", reasoning_chars=5))

    assert not result.success and sandbox.files == {}
    assert "no answer" in result.error.lower()


def test_df_live_02_max_tokens_is_never_below_one():
    harness = LocalCoderHarness(max_num_ctx=16384)
    with patch("dark_factory.harness.local_coder.requests.post", side_effect=_prism_only(_prism_ok())) as post:
        _, telemetry = harness._call_model("sys", "user", output_reserve=0)
    assert post.call_args.kwargs["json"]["max_tokens"] == 1
    assert telemetry.max_tokens == 1
