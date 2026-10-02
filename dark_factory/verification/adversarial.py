"""Adversarial Red-Team Auditor for the Sovereign Dark Factory."""

from __future__ import annotations

from dark_factory.domain.types import AdversarialFinding, AdversarialReport
from dark_factory.harness.llm_text import cap_text, clean_text, extract_json_object, fence
from dark_factory.harness.local_coder import LocalCoderHarness

_SEVERITIES = ("INFO", "WARN", "CRITICAL")
MAX_AUDIT_PATCH_CHARS = 12000  # about 4000 estimated tokens; keeps the audit prompt inside the default window

_ADVERSARIAL_SYSTEM_PROMPT = """You are the Lead Adversarial Auditor (Red Team) in the Sovereign Dark Factory.
Your job is to aggressively audit a proposed code patch and identify reasons why it should NOT be approved.
You evaluate the patch across 4 mandatory dimensions:
1. anti-cheating: Hardcoded return values, commented-out assertions, deleted test files, or mocks bypassing real logic.
2. boundary: Unhandled null/None inputs, empty collections, division by zero, type mismatches, or missing edge cases.
3. security: Path traversal (directory escaping), unsafe subprocess execution, shell injection, or secret exposure.
4. regression: Performance degradation (e.g. O(N^2) loops), broken existing interfaces, or leaky abstractions.

Format Rules:
You must respond ONLY with a valid JSON object matching this schema:
{
  "passed": true | false,
  "summary": "<high-level evaluation summary>",
  "findings": [
    {
      "severity": "INFO" | "WARN" | "CRITICAL",
      "category": "anti-cheating" | "boundary" | "security" | "regression",
      "summary": "<one-line summary of finding>",
      "details": "<detailed explanation with line numbers if applicable>"
    }
  ]
}
If no defects are found, set "passed": true, "summary": "No defects found.", "findings": [].
Any CRITICAL or WARN finding should set "passed": false.
Do not wrap your JSON in conversational prose or explanations. Output JSON only."""


class AdversarialAuditor:
    """Local-first red-team auditor that evaluates patches before human review."""

    def __init__(self, harness: LocalCoderHarness | None = None) -> None:
        self.harness = harness or LocalCoderHarness()

    def audit_patch(
        self,
        task_prompt: str,
        patch: str,
        gate_summary: str = "",
    ) -> AdversarialReport:
        """Audit a unified diff against task requirements and adversarial invariants."""
        if not patch or not patch.strip():
            return AdversarialReport(
                passed=False,
                summary="Empty patch: nothing to audit.",
                findings=[
                    AdversarialFinding(
                        severity="WARN",
                        category="boundary",
                        summary="Empty patch",
                        details="No code was modified in this run.",
                    )
                ],
            )

        system_prompt = _ADVERSARIAL_SYSTEM_PROMPT
        audited, truncated = cap_text(patch, MAX_AUDIT_PATCH_CHARS)
        user_prompt = self._build_user_prompt(task_prompt, audited, gate_summary)

        try:
            raw_text, _telemetry = self.harness._call_model(system_prompt, user_prompt)
            report = self._parse_response(raw_text)
            if truncated:
                report.findings.append(
                    AdversarialFinding(
                        severity="INFO",
                        category="regression",
                        summary="Diff truncated for the audit",
                        details=f"Only about {MAX_AUDIT_PATCH_CHARS} of {len(patch)} patch characters fit the model's window.",
                    )
                )
            return report
        except Exception as exc:
            return AdversarialReport(
                passed=False,
                summary=f"Adversarial auditor execution error: {exc}",
                findings=[
                    AdversarialFinding(
                        severity="WARN",
                        category="regression",
                        summary="Auditor execution failed",
                        details=str(exc),
                    )
                ],
            )

    def _build_user_prompt(self, task_prompt: str, patch: str, gate_summary: str) -> str:
        gates_block = f"\nVERIFICATION GATES STATUS:\n{gate_summary}\n" if gate_summary.strip() else ""
        return (
            f"TASK SPECIFICATION:\n{task_prompt}\n"
            f"{gates_block}\n"
            f"PROPOSED UNIFIED DIFF:\n{fence(patch, 'diff')}\n\n"
            "Audit the patch above according to the 4 adversarial dimensions. Return JSON only."
        )

    def _parse_response(self, raw_text: str) -> AdversarialReport:
        """Parse raw model output into structured AdversarialReport with graceful fallback."""
        try:
            data = extract_json_object(raw_text, keys=("findings", "summary", "passed"))
            findings: list[AdversarialFinding] = []
            for item in data.get("findings", []):
                severity = str(item.get("severity", "WARN")).strip().upper()
                findings.append(
                    AdversarialFinding(
                        severity=severity if severity in _SEVERITIES else "WARN",
                        category=clean_text(str(item.get("category", "boundary")).lower()),
                        summary=clean_text(str(item.get("summary", "Unspecified finding"))),
                        details=clean_text(str(item.get("details", ""))),
                    )
                )

            # The model's own "passed" flag is advisory text; the verdict is derived from the findings.
            if data.get("passed") is False and not findings:
                findings.append(
                    AdversarialFinding(
                        severity="WARN",
                        category="regression",
                        summary="Auditor flagged a failure without findings",
                        details=clean_text(str(data.get("summary", ""))),
                    )
                )
            passed = not any(f.severity in ("WARN", "CRITICAL") for f in findings)
            summary = clean_text(str(data.get("summary", "Audit completed.")))

            return AdversarialReport(
                passed=passed,
                summary=summary,
                findings=findings,
            )
        except Exception as exc:
            return AdversarialReport(
                passed=False,
                summary=f"Adversarial audit produced unparseable output: {exc}",
                findings=[
                    AdversarialFinding(
                        severity="WARN",
                        category="regression",
                        summary="Malformed auditor response",
                        details=raw_text[:500],
                    )
                ],
            )
