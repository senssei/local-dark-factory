"""Unit tests for dark_factory.verification.adversarial."""

from __future__ import annotations

from unittest.mock import MagicMock

from dark_factory.domain.types import ModelTelemetry


def test_adversarial_auditor_empty_patch():
    from dark_factory.verification.adversarial import AdversarialAuditor

    harness = MagicMock()
    auditor = AdversarialAuditor(harness=harness)

    report = auditor.audit_patch(task_prompt="Implement foo", patch="")
    assert not report.passed
    assert "empty patch" in report.summary.lower()
    # Model should not have been called for empty patch
    harness._call_model.assert_not_called()


def test_adversarial_auditor_parses_clean_json():
    from dark_factory.verification.adversarial import AdversarialAuditor

    harness = MagicMock()
    harness._call_model.return_value = (
        '{"passed": true, "summary": "No defects found.", "findings": []}',
        ModelTelemetry("ollama", "qwen2.5-coder:14b"),
    )
    auditor = AdversarialAuditor(harness=harness)

    diff = "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-old\n+new\n"
    report = auditor.audit_patch(task_prompt="Refactor foo", patch=diff)

    assert report.passed
    assert report.summary == "No defects found."
    assert len(report.findings) == 0
    harness._call_model.assert_called_once()


def test_adversarial_auditor_parses_findings_with_fences():
    from dark_factory.verification.adversarial import AdversarialAuditor

    mock_json = """```json
{
  "passed": false,
  "summary": "Security and cheating defects detected",
  "findings": [
    {
      "severity": "CRITICAL",
      "category": "security",
      "summary": "Path traversal in open()",
      "details": "User input passed to open without path sanitization on line 12"
    },
    {
      "severity": "WARN",
      "category": "anti-cheating",
      "summary": "Hardcoded test assertion",
      "details": "Function contains hardcoded return for test value"
    }
  ]
}
```"""
    harness = MagicMock()
    harness._call_model.return_value = (mock_json, ModelTelemetry("ollama", "qwen2.5-coder:14b"))
    auditor = AdversarialAuditor(harness=harness)

    diff = "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n+open(path)\n"
    report = auditor.audit_patch(task_prompt="Add file reader", patch=diff)

    assert not report.passed
    assert len(report.findings) == 2
    assert report.findings[0].severity == "CRITICAL"
    assert report.findings[0].category == "security"
    assert report.findings[1].severity == "WARN"
    assert report.findings[1].category == "anti-cheating"


def test_adversarial_auditor_handles_malformed_json_fallback():
    from dark_factory.verification.adversarial import AdversarialAuditor

    harness = MagicMock()
    harness._call_model.return_value = (
        "I am an AI that thinks this patch looks okay overall. No JSON here!",
        ModelTelemetry("ollama", "qwen2.5-coder:14b"),
    )
    auditor = AdversarialAuditor(harness=harness)

    diff = "--- a/calc.py\n+++ b/calc.py\n@@ -1 +1 @@\n+return 42\n"
    report = auditor.audit_patch(task_prompt="Implement calc", patch=diff)

    assert not report.passed
    assert "unparseable" in report.summary.lower()
    assert len(report.findings) == 1
    assert report.findings[0].severity == "WARN"
    assert report.findings[0].category == "regression"


def test_adversarial_auditor_harness_exception_handled():
    from dark_factory.verification.adversarial import AdversarialAuditor

    harness = MagicMock()
    harness._call_model.side_effect = RuntimeError("Ollama connection timed out")
    auditor = AdversarialAuditor(harness=harness)

    diff = "--- a/fix.py\n+++ b/fix.py\n@@ -1 +1 @@\n+x = 1\n"
    report = auditor.audit_patch(task_prompt="Quick fix", patch=diff)

    assert not report.passed
    assert "Ollama connection timed out" in report.summary
    assert len(report.findings) == 1
    assert report.findings[0].category == "regression"


def test_adversarial_auditor_includes_gate_summary():
    from dark_factory.verification.adversarial import AdversarialAuditor

    harness = MagicMock()
    harness._call_model.return_value = (
        '{"passed": true, "summary": "Clean", "findings": []}',
        ModelTelemetry("ollama", "qwen2.5-coder:14b"),
    )
    auditor = AdversarialAuditor(harness=harness)

    diff = "--- a/main.py\n+++ b/main.py\n@@ -1 +1 @@\n+pass\n"
    auditor.audit_patch(
        task_prompt="Test gate summary",
        patch=diff,
        gate_summary="Step pytest: PASSED\nStep ruff: PASSED",
    )

    args, _ = harness._call_model.call_args
    user_prompt = args[1]
    assert "Step pytest: PASSED" in user_prompt
    assert "PROPOSED UNIFIED DIFF:" in user_prompt


def _ollama_json(text: str):
    class _Resp:
        status_code = 200

        def json(self):
            return {"response": text, "prompt_eval_count": 3000, "eval_count": 20}

    return _Resp()


def test_auditor_caps_a_large_patch_instead_of_failing_the_preflight():
    from unittest.mock import patch

    from dark_factory.harness import LocalCoderHarness
    from dark_factory.verification.adversarial import AdversarialAuditor

    big_patch = "+x\n" * 9000  # 27 KB, over the prompt window without a cap
    reply = '{"passed": true, "summary": "ok", "findings": []}'
    with patch("dark_factory.harness.local_coder.requests.post", return_value=_ollama_json(reply)) as post:
        report = AdversarialAuditor(harness=LocalCoderHarness(max_num_ctx=8192)).audit_patch("task", big_patch)
    post.assert_called_once()
    assert "execution error" not in report.summary.lower()
    assert any(f.severity == "INFO" and "truncated" in f.summary.lower() for f in report.findings)
    assert report.passed  # INFO never flips the verdict


def test_mutator_caps_a_large_patch_instead_of_failing_the_preflight():
    from unittest.mock import patch

    from dark_factory.harness import LocalCoderHarness
    from dark_factory.verification.adversarial_mutator import AdversarialMutator

    reply = "```python\ndef test_x():\n    assert True\n```"
    with patch("dark_factory.harness.local_coder.requests.post", return_value=_ollama_json(reply)) as post:
        code = AdversarialMutator(harness=LocalCoderHarness(max_num_ctx=8192)).generate_probe("task", "+x\n" * 9000)
    post.assert_called_once()
    assert code is not None
