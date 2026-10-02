"""Unit tests for dark_factory.dashboard.views — pure functions, no server needed."""

from dark_factory.dashboard.views import (
    render_diff,
    render_eval_view,
    render_layout,
    render_run_detail,
    render_runs_list,
)
from dark_factory.domain.types import (
    EvidenceManifest,
    ModelTelemetry,
    PhaseTiming,
    RunStatus,
    StepExecution,
)
from dark_factory.eval.runner import EvalReport, EvalRunResult


def test_render_layout_includes_title_and_nav():
    html = render_layout("My Title", "<p>body</p>")
    assert "My Title" in html
    assert 'href="/"' in html
    assert 'href="/eval"' in html
    assert "<p>body</p>" in html


def test_render_layout_escapes_title():
    html = render_layout("<script>alert(1)</script>", "body")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_runs_list_empty():
    assert "No runs" in render_runs_list([])


def test_render_runs_list_renders_run_link_and_status():
    runs = [
        EvidenceManifest(
            run_id="run-abc123",
            repo_path="/tmp/repo",
            base_rev="deadbeefcafebabe",
            status=RunStatus.AWAITING_REVIEW,
            created_at="2026-09-29T00:00:00Z",
        )
    ]
    html = render_runs_list(runs)
    assert 'href="/runs/run-abc123"' in html
    assert "run-abc123" in html
    assert "AWAITING_REVIEW" in html
    assert "/tmp/repo" in html


def _manifest(**overrides) -> EvidenceManifest:
    base = dict(
        run_id="run-x",
        status=RunStatus.AWAITING_REVIEW,
        repo_path="/tmp/repo",
        base_rev="abc123",
        created_at="2026-09-29T00:00:00Z",
        completed_at="2026-09-29T00:01:00Z",
    )
    base.update(overrides)
    return EvidenceManifest(**base)


def test_render_run_detail_basic_fields():
    manifest = _manifest()
    html = render_run_detail(manifest, "diff --git a/x b/x\n+hello\n")
    assert "AWAITING_REVIEW" in html
    assert "/tmp/repo" in html
    assert "abc123" in html
    assert "diff --git a/x b/x" in html


def test_render_run_detail_escapes_operator_notes():
    manifest = _manifest(operator_notes="<script>alert('xss')</script>")
    html = render_run_detail(manifest, "")
    assert "<script>alert('xss')</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_run_detail_escapes_diff_content():
    manifest = _manifest()
    html = render_run_detail(manifest, "<script>evil()</script>")
    assert "<script>evil()</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_run_detail_shows_empty_diff_placeholder():
    manifest = _manifest()
    html = render_run_detail(manifest, "")
    assert "No diff generated" in html


def test_render_run_detail_shows_stuck_detector_when_nonzero():
    manifest = _manifest(repeated_failure_streak=2)
    html = render_run_detail(manifest, "")
    assert "Stuck Detector" in html
    assert "3 time(s)" in html


def test_render_run_detail_hides_stuck_detector_when_zero():
    manifest = _manifest(repeated_failure_streak=0)
    html = render_run_detail(manifest, "")
    assert "Stuck Detector" not in html


def test_render_run_detail_shows_telemetry_and_phase_timings():
    manifest = _manifest(
        model_telemetry=ModelTelemetry(
            engine="ollama", model_name="qwen2.5-coder:14b", completion_tokens=42, tokens_per_sec=10.5
        ),
        phase_timings=[PhaseTiming(phase="sandbox_create", duration_sec=0.02, started_at="2026-09-29T00:00:00Z")],
        verification_results=[StepExecution(step_id="pytest", exit_code=0, stdout="ok", stderr="", duration_sec=0.1)],
    )
    html = render_run_detail(manifest, "")
    assert "ollama" in html
    assert "qwen2.5-coder:14b" in html
    assert "sandbox_create" in html
    assert "pytest" in html
    assert "PASSED" in html


def test_render_diff_empty_shows_placeholder():
    assert "No diff generated" in render_diff("")
    assert "No diff generated" in render_diff("   \n")


def test_render_diff_classifies_added_and_removed_lines():
    patch = (
        "diff --git a/calc.py b/calc.py\n"
        "index abc123..def456 100644\n"
        "--- a/calc.py\n"
        "+++ b/calc.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def add(a, b):\n"
        "-    return a - b\n"
        "+    return a + b\n"
    )
    html = render_diff(patch)
    assert '<span class="diff-meta">diff --git a/calc.py b/calc.py</span>' in html
    assert '<span class="diff-file">--- a/calc.py</span>' in html
    assert '<span class="diff-file">+++ b/calc.py</span>' in html
    assert '<span class="diff-hunk">@@ -1,2 +1,2 @@</span>' in html
    assert '<span class="diff-del">-    return a - b</span>' in html
    assert '<span class="diff-add">+    return a + b</span>' in html
    assert '<span class="diff-context"> def add(a, b):</span>' in html


def test_render_diff_escapes_line_content():
    html = render_diff("+<script>evil()</script>\n")
    assert "<script>evil()</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_eval_view_empty():
    assert "No eval reports" in render_eval_view([])


def test_render_eval_view_shows_latest_summary_and_history():
    report1 = EvalReport(
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
    report2 = EvalReport(
        started_at="2026-09-29T01:00:00Z",
        finished_at="2026-09-29T01:01:00Z",
        model="qwen2.5-coder:14b",
        ollama_url="http://localhost:11434",
        prism_url="http://127.0.0.1:5272/v1",
        results=[
            EvalRunResult(
                scenario="primes",
                run_id="eval-primes-2",
                converged=False,
                status="FAILED",
                healing_attempts=5,
                repeated_failure_streak_fired=True,
                duration_sec=2.0,
            )
        ],
    )
    html = render_eval_view([report1, report2])
    assert "Latest Report" in html
    assert "primes" in html
    assert "History" in html
    assert "yes" in html  # latest (report2) has any_stuck=True


def test_render_run_detail_shows_adversarial_report_clean():
    from dark_factory.domain.types import AdversarialReport

    manifest = _manifest(
        adversarial_report=AdversarialReport(
            passed=True,
            summary="Zero adversarial findings detected.",
            findings=[],
        )
    )
    html = render_run_detail(manifest, "")
    assert "Adversarial Audit" in html
    assert "PASS" in html
    assert "Zero adversarial findings detected." in html
    assert "No adversarial findings" in html


def test_render_run_detail_shows_adversarial_report_with_findings_and_escapes():
    from dark_factory.domain.types import AdversarialFinding, AdversarialReport

    manifest = _manifest(
        adversarial_report=AdversarialReport(
            passed=False,
            summary="Critical cheating pattern detected.",
            findings=[
                AdversarialFinding(
                    severity="CRITICAL",
                    category="anti-cheating",
                    summary="<script>alert('cheat')</script>",
                    details="Unsafe <injection> detected in <code> logic.",
                ),
                AdversarialFinding(
                    severity="WARN",
                    category="boundary",
                    summary="Off-by-one boundary flaw",
                    details="Negative bounds not checked.",
                ),
            ],
        )
    )
    html = render_run_detail(manifest, "")
    assert "Adversarial Audit" in html
    assert "WARN" in html
    assert "Critical cheating pattern detected." in html
    assert "CRITICAL" in html
    assert "anti-cheating" in html
    assert "<script>alert('cheat')</script>" not in html
    assert "&lt;script&gt;alert(&#x27;cheat&#x27;)&lt;/script&gt;" in html
    assert "&lt;injection&gt;" in html
    assert "Off-by-one boundary flaw" in html


def test_render_run_detail_hides_adversarial_card_when_none():
    manifest = _manifest(adversarial_report=None)
    html = render_run_detail(manifest, "")
    assert "Adversarial Audit" not in html


def test_render_run_detail_shows_execution_plan_and_escapes():
    from dark_factory.domain.types import ExecutionPlan

    manifest = _manifest(
        execution_plan=ExecutionPlan(
            plan_id="plan-xss",
            summary="<script>alert('plan')</script>",
            invariants=["<invariant>safe</invariant>"],
            steps=["1. <step>one</step>"],
            target_files=["<target>.py"],
        )
    )
    html = render_run_detail(manifest, "")
    assert "Execution Plan" in html
    assert "<script>alert('plan')</script>" not in html
    assert "&lt;script&gt;alert(&#x27;plan&#x27;)&lt;/script&gt;" in html
    assert "&lt;invariant&gt;safe&lt;/invariant&gt;" in html
    assert "&lt;step&gt;one&lt;/step&gt;" in html
    assert "&lt;target&gt;.py" in html


def test_render_run_detail_hides_execution_plan_when_none():
    manifest = _manifest(execution_plan=None)
    html = render_run_detail(manifest, "")
    assert "Execution Plan" not in html


def test_render_run_detail_shows_active_mutation_and_escapes():
    manifest = _manifest(
        adversarial_test_code="def test_xss():\n    assert '<script>bad</script>' != ''\n",
    )
    html = render_run_detail(manifest, "")
    assert "Active Adversarial Mutation" in html
    assert "Probe Synthesized" in html
    assert "<script>bad</script>" not in html
    assert "&lt;script&gt;bad&lt;/script&gt;" in html


def test_render_run_detail_hides_active_mutation_when_none():
    manifest = _manifest(adversarial_test_code=None)
    html = render_run_detail(manifest, "")
    assert "Active Adversarial Mutation" not in html
