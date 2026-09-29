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
