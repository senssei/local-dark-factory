"""Pure HTML-rendering functions for the read-only dashboard.

No template engine (stdlib-only, per Phase 12's design) — every interpolated value goes through
`html.escape()`. These functions take no I/O; they're independently unit-testable against hand-built data.
"""

from __future__ import annotations

from html import escape

from dark_factory.domain.types import EvidenceManifest
from dark_factory.eval.runner import EvalReport

_STYLE = """
body { font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif; margin: 0; background: #0f1115;
       color: #e6e6e6; }
header { background: #171a21; padding: 1rem 1.5rem; border-bottom: 1px solid #2a2e37; }
header a { color: #e6e6e6; text-decoration: none; margin-right: 1.5rem; font-weight: 600; }
header a:hover { color: #7dd3fc; }
main { padding: 1.5rem; max-width: 1100px; margin: 0 auto; }
table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
th, td { text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid #2a2e37; }
th { color: #9ca3af; font-weight: 600; font-size: 0.85rem; text-transform: uppercase; }
tr:hover td { background: #171a21; }
a.run-link { color: #7dd3fc; text-decoration: none; font-family: monospace; }
a.run-link:hover { text-decoration: underline; }
.status { padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.8rem; font-weight: 600; }
.status-AWAITING_REVIEW { background: #3b2f0b; color: #fbbf24; }
.status-APPROVED { background: #0b3b1e; color: #34d399; }
.status-REJECTED, .status-FAILED { background: #3b0b0b; color: #f87171; }
.status-TIMED_OUT, .status-CANCELLED { background: #2a2e37; color: #9ca3af; }
pre { background: #171a21; padding: 1rem; overflow-x: auto; border-radius: 6px; border: 1px solid #2a2e37; }
.field { margin: 0.25rem 0; }
.field b { color: #9ca3af; display: inline-block; min-width: 11rem; }
.badge-stuck { color: #f87171; font-weight: 600; }
.badge-pass { background: #0b3b1e; color: #34d399; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.8rem; font-weight: 600; }
.badge-warn { background: #3b2f0b; color: #fbbf24; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.8rem; font-weight: 600; }
.badge-critical { background: #3b0b0b; color: #f87171; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.8rem; font-weight: 600; }
.badge-info { background: #1e293b; color: #94a3b8; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.8rem; font-weight: 600; }
pre.diff {
    padding: 0.5rem 0; line-height: 1.6; font-size: 0.9rem;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
}
pre.diff span {
    display: block; padding: 0.1rem 1rem 0.1rem 0.75rem; white-space: pre-wrap; word-break: break-word;
    border-left: 3px solid transparent;
}
pre.diff .diff-add { background: rgba(52, 211, 153, 0.1); color: #a7f3d0; border-left-color: #34d399; }
pre.diff .diff-del { background: rgba(248, 113, 113, 0.1); color: #fecaca; border-left-color: #f87171; }
pre.diff .diff-hunk {
    background: rgba(125, 211, 252, 0.08); color: #7dd3fc; font-weight: 600; margin-top: 0.4rem;
}
pre.diff .diff-file { color: #e5e7eb; font-weight: 600; }
pre.diff .diff-meta { color: #4b5563; font-size: 0.85em; }
pre.diff .diff-context { color: #8b93a1; }
"""


def render_layout(title: str, body: str) -> str:
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{escape(title)} — Dark Factory Dashboard</title>
<style>{_STYLE}</style>
</head>
<body>
<header>
<a href="/">Runs</a>
<a href="/eval">Eval</a>
</header>
<main>
<h1>{escape(title)}</h1>
{body}
</main>
</body>
</html>"""


def _status_badge(status: str) -> str:
    return f'<span class="status status-{escape(status)}">{escape(status)}</span>'


def _diff_line_class(line: str) -> str:
    if line.startswith("+++") or line.startswith("---"):
        return "diff-file"
    if line.startswith("@@"):
        return "diff-hunk"
    if line.startswith("+"):
        return "diff-add"
    if line.startswith("-"):
        return "diff-del"
    if line.startswith(("diff --git", "index ", "new file mode", "deleted file mode", "similarity index")):
        return "diff-meta"
    return "diff-context"


def render_diff(patch: str) -> str:
    """Render a unified diff with GitHub-style add/remove line highlighting (no syntax-highlighting
    library — a handful of CSS classes keyed off the standard unified-diff line prefixes)."""
    if not patch.strip():
        return "<p>(No diff generated)</p>"

    lines = [f'<span class="{_diff_line_class(line)}">{escape(line) or "&nbsp;"}</span>' for line in patch.splitlines()]
    body = "\n".join(lines)
    return f'<pre class="diff">{body}</pre>'


def render_runs_list(runs: list[EvidenceManifest]) -> str:
    if not runs:
        return "<p>No runs recorded yet.</p>"

    rows = []
    for r in runs:
        run_id = escape(r.run_id)
        rows.append(
            "<tr>"
            f'<td><a class="run-link" href="/runs/{run_id}">{run_id}</a></td>'
            f"<td>{_status_badge(r.status.value)}</td>"
            f"<td>{escape(r.repo_path)}</td>"
            f"<td>{escape(r.base_rev[:10])}</td>"
            f"<td>{escape(r.created_at)}</td>"
            "</tr>"
        )
    table = (
        "<table><thead><tr><th>Run ID</th><th>Status</th><th>Repo</th><th>Base Rev</th>"
        f"<th>Created</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )
    return table


def render_run_detail(manifest: EvidenceManifest, patch: str) -> str:
    fields = [
        ("Status", _status_badge(manifest.status.value)),
        ("Repository", escape(manifest.repo_path)),
        ("Base Revision", escape(manifest.base_rev)),
        ("Created At", escape(manifest.created_at)),
        ("Completed At", escape(manifest.completed_at or "In Progress")),
        ("Healing Retries", str(manifest.healing_attempts)),
    ]
    if manifest.repeated_failure_streak:
        fields.append(
            (
                "Stuck Detector",
                f'<span class="badge-stuck">repeated the same failure '
                f"{manifest.repeated_failure_streak + 1} time(s)</span>",
            )
        )
    if manifest.resulting_rev:
        fields.append(("Resulting Revision", escape(manifest.resulting_rev)))
    if manifest.operator_notes:
        fields.append(("Operator Notes", escape(manifest.operator_notes)))

    fields_html = "".join(f'<div class="field"><b>{label}:</b> {value}</div>' for label, value in fields)

    telemetry_html = ""
    if manifest.model_telemetry:
        t = manifest.model_telemetry
        telemetry_html = (
            "<h2>Telemetry</h2>"
            f'<div class="field"><b>Engine:</b> {escape(t.engine)} ({escape(t.model_name)})</div>'
            f'<div class="field"><b>Tokens:</b> {t.completion_tokens} generated @ {t.tokens_per_sec} tok/s</div>'
            f'<div class="field"><b>Cloud Cost:</b> ${t.cost_usd:.2f}</div>'
        )

    plan_html = ""
    if manifest.execution_plan:
        plan = manifest.execution_plan
        invariants_html = (
            "".join(f"<li><code>{escape(inv)}</code></li>" for inv in plan.invariants)
            if plan.invariants
            else "<li>None</li>"
        )
        steps_html = "".join(f"<li>{escape(step)}</li>" for step in plan.steps) if plan.steps else "<li>None</li>"
        files_html = (
            ", ".join(f"<code>{escape(tf)}</code>" for tf in plan.target_files) if plan.target_files else "None"
        )
        plan_html = (
            "<h2>Execution Plan</h2>"
            f'<div class="field"><b>Plan ID:</b> {escape(plan.plan_id)}</div>'
            f'<div class="field"><b>Summary:</b> {escape(plan.summary)}</div>'
            f'<div class="field"><b>Target Files:</b> {files_html}</div>'
            f"<h3>Architectural Invariants</h3><ul>{invariants_html}</ul>"
            f"<h3>Implementation Steps</h3><ul>{steps_html}</ul>"
        )

    gates_html = "<p>No verification gates recorded.</p>"
    if manifest.verification_results:
        rows = []
        for res in manifest.verification_results:
            outcome = "PASSED" if res.passed else f"FAILED (exit {res.exit_code})"
            rows.append(f"<li><code>{escape(res.step_id)}</code>: {escape(outcome)} ({res.duration_sec:.2f}s)</li>")
        gates_html = f"<ul>{''.join(rows)}</ul>"

    adv_html = ""
    if manifest.adversarial_report:
        adv = manifest.adversarial_report
        overall = adv.badge
        overall_badge = f'<span class="badge-{overall.lower()}">{overall}</span>'
        findings_html = "<p>No adversarial findings recorded.</p>"
        if adv.findings:
            rows = []
            for f in adv.findings:
                sev_cls = f"badge-{escape(f.severity.lower(), quote=True)}"
                badge = f'<span class="{sev_cls}">{escape(f.severity)}</span>'
                details_html = f"<br><small>{escape(f.details)}</small>" if f.details else ""
                rows.append(
                    f"<tr><td>{badge}</td><td><code>{escape(f.category)}</code></td>"
                    f"<td><b>{escape(f.summary)}</b>{details_html}</td></tr>"
                )
            findings_html = (
                "<table><thead><tr><th>Severity</th><th>Category</th><th>Details</th></tr></thead>"
                f"<tbody>{''.join(rows)}</tbody></table>"
            )
        adv_html = f"<h2>Adversarial Audit {overall_badge}</h2><p>{escape(adv.summary)}</p>{findings_html}"

    mutation_html = ""
    if manifest.adversarial_test_code:
        mutation_html = (
            "<h2>Active Adversarial Mutation</h2>"
            '<span class="badge-pass">Probe Synthesized</span>'
            f"<pre><code>{escape(manifest.adversarial_test_code)}</code></pre>"
        )

    analysis_html = ""
    if manifest.analysis_report:
        rep = manifest.analysis_report
        res = rep.resources
        rows = []
        for f in rep.findings:
            sev_cls = f"badge-{escape(f.severity.lower(), quote=True)}"
            details_html = f"<br><small>{escape(f.details)}</small>" if f.details else ""
            rows.append(
                f'<tr><td><span class="{sev_cls}">{escape(f.severity)}</span></td>'
                f"<td><code>{escape(f.category)}</code></td><td><b>{escape(f.summary)}</b>{details_html}</td></tr>"
            )
        table = (
            "<table><thead><tr><th>Severity</th><th>Category</th><th>Details</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
            if rows
            else "<p>No findings.</p>"
        )
        metrics = "".join(f"<li>{escape(str(k))}: {escape(str(v))}</li>" for k, v in rep.metrics.items())
        analysis_html = (
            f'<h2>Performance &amp; Quality Analysis <span class="badge-{rep.badge.lower()}">{rep.badge}</span></h2>'
            f"<p>{escape(rep.summary)}</p>"
            f"<ul><li>VRAM: {res.peak_vram_mb} / {res.vram_total_mb} MiB (GPU util {res.avg_gpu_util_pct}%)</li>"
            f"<li>RAM: {res.peak_ram_mb} / {res.ram_total_mb} MiB ({res.samples} samples)</li>{metrics}</ul>"
            f"{table}"
        )

    timings_html = ""
    if manifest.phase_timings:
        rows = [f"<li>{escape(pt.phase)}: {pt.duration_sec:.2f}s</li>" for pt in manifest.phase_timings]
        timings_html = f"<h2>Phase Timings</h2><ul>{''.join(rows)}</ul>"

    diff_html = render_diff(patch)

    return (
        f"{fields_html}"
        f"{telemetry_html}"
        f"{plan_html}"
        f"<h2>Verification Gates</h2>{gates_html}"
        f"{adv_html}"
        f"{mutation_html}"
        f"{analysis_html}"
        f"{timings_html}"
        f"<h2>Unified Diff</h2>{diff_html}"
    )


def render_eval_view(reports: list[EvalReport]) -> str:
    if not reports:
        return "<p>No eval reports yet. Run <code>dark-factory eval</code> to generate one.</p>"

    latest = reports[-1]
    latest_summary = latest.scenario_summary()

    rows = []
    for name, s in latest_summary.items():
        stuck = '<span class="badge-stuck">yes</span>' if s["any_stuck"] else "no"
        rows.append(
            "<tr>"
            f"<td>{escape(name)}</td>"
            f"<td>{s['attempts']}</td>"
            f"<td>{s['converged']}</td>"
            f"<td>{s['convergence_rate']:.0%}</td>"
            f"<td>{s['avg_healing_attempts']:.1f}</td>"
            f"<td>{stuck}</td>"
            "</tr>"
        )
    latest_table = (
        f"<h2>Latest Report ({escape(latest.model)}, {escape(latest.started_at)})</h2>"
        "<table><thead><tr><th>Scenario</th><th>Attempts</th><th>Converged</th><th>Rate</th>"
        f"<th>Avg Healing</th><th>Stuck?</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )

    trend_html = ""
    if len(reports) > 1:
        trend_rows = []
        for report in reports:
            summary = report.scenario_summary()
            overall_attempts = sum(s["attempts"] for s in summary.values())
            overall_converged = sum(s["converged"] for s in summary.values())
            rate = overall_converged / overall_attempts if overall_attempts else 0.0
            trend_rows.append(
                "<tr>"
                f"<td>{escape(report.started_at)}</td>"
                f"<td>{escape(report.model)}</td>"
                f"<td>{overall_converged}/{overall_attempts}</td>"
                f"<td>{rate:.0%}</td>"
                "</tr>"
            )
        trend_html = (
            "<h2>History</h2>"
            "<table><thead><tr><th>Started</th><th>Model</th><th>Converged</th><th>Rate</th></tr></thead>"
            f"<tbody>{''.join(trend_rows)}</tbody></table>"
        )

    return latest_table + trend_html
