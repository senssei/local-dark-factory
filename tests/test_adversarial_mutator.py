"""Unit tests for dark_factory.verification.adversarial_mutator."""

from __future__ import annotations

import ast
from unittest.mock import MagicMock

from dark_factory.domain.types import ModelTelemetry


def test_adversarial_mutator_empty_patch():
    from dark_factory.verification.adversarial_mutator import AdversarialMutator

    harness = MagicMock()
    mutator = AdversarialMutator(harness=harness)

    probe = mutator.generate_probe(task_prompt="Implement foo", patch="")
    assert probe is None
    harness._call_model.assert_not_called()


def test_adversarial_mutator_generates_valid_python_probe():
    from dark_factory.verification.adversarial_mutator import AdversarialMutator

    valid_test = """```python
import pytest
from calc import add

def test_add_extreme_boundaries():
    assert add(1e12, 1e12) == 2e12

def test_add_negative_infinity():
    with pytest.raises(OverflowError):
        add(float('inf'), 1)
```"""
    harness = MagicMock()
    harness._call_model.return_value = (valid_test, ModelTelemetry("ollama", "qwen2.5-coder:14b"))
    mutator = AdversarialMutator(harness=harness)

    diff = "--- a/calc.py\n+++ b/calc.py\n@@ -1 +1,2 @@\n+def add(a, b):\n+    return a + b\n"
    probe = mutator.generate_probe(task_prompt="Add calculator add function", patch=diff)

    assert probe is not None
    assert "def test_add_extreme_boundaries():" in probe
    assert "```" not in probe
    # ast.parse must validate it successfully
    tree = ast.parse(probe)
    assert len(tree.body) > 0

    args, _ = harness._call_model.call_args
    user_prompt = args[1]
    assert "def add(a, b):" in user_prompt
    assert "Add calculator add function" in user_prompt


def test_adversarial_mutator_rejects_syntax_errors():
    from dark_factory.verification.adversarial_mutator import AdversarialMutator

    broken_code = """```python
def test_syntax_error(
    this is completely invalid python code !!!
```"""
    harness = MagicMock()
    harness._call_model.return_value = (broken_code, ModelTelemetry("ollama", "qwen2.5-coder:14b"))
    mutator = AdversarialMutator(harness=harness)

    diff = "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n+pass\n"
    probe = mutator.generate_probe(task_prompt="Implement foo", patch=diff)

    # Broken syntax must be safely rejected without raising an unhandled exception
    assert probe is None


def test_adversarial_mutator_handles_harness_exception():
    from dark_factory.verification.adversarial_mutator import AdversarialMutator

    harness = MagicMock()
    harness._call_model.side_effect = RuntimeError("Inference connection failed")
    mutator = AdversarialMutator(harness=harness)

    diff = "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n+pass\n"
    probe = mutator.generate_probe(task_prompt="Implement foo", patch=diff)

    assert probe is None


def test_adversarial_mutator_raw_python_without_fences():
    from dark_factory.verification.adversarial_mutator import AdversarialMutator

    raw_python = "def test_raw():\n    assert 1 + 1 == 2\n"
    harness = MagicMock()
    harness._call_model.return_value = (raw_python, ModelTelemetry("ollama", "qwen2.5-coder:14b"))
    mutator = AdversarialMutator(harness=harness)

    diff = "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n+pass\n"
    probe = mutator.generate_probe(task_prompt="Implement foo", patch=diff)

    assert probe is not None
    assert "def test_raw():" in probe
    assert ast.parse(probe)
