"""Unit tests for dark_factory.analysis.analyzer."""

from dark_factory.domain.types import (
    EvidenceManifest,
    ModelTelemetry,
    PhaseTiming,
    ResourceUsage,
    TaskSpec,
)


def _manifest(tps: float = 40.0, healing: int = 0, phases=None) -> EvidenceManifest:
    m = EvidenceManifest.create(run_id="r", repo_path="/tmp/r", base_rev="abc")
    m.healing_attempts = healing
    m.model_telemetry = ModelTelemetry(engine="ollama", model_name="m", tokens_per_sec=tps)
    m.phase_timings = phases or [
        PhaseTiming("sandbox_create", 1.0, "t"),
        PhaseTiming("agent_and_verify", 9.0, "t"),
    ]
    return m


def _spec(max_heal: int = 3) -> TaskSpec:
    return TaskSpec(repo_path="/tmp/r", task_prompt="x", max_healing_attempts=max_heal)


def _diff(path: str, added: list[str], start: int = 1) -> str:
    body = "".join(f"+{line}\n" for line in added)
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -0,0 +{start},{len(added)} @@\n{body}"


def _categories(report, severity="WARN"):
    return {f.category + ":" + f.summary.split()[0] for f in report.findings if f.severity == severity}


def test_clean_run_is_pass_and_reports_metrics():
    from dark_factory.analysis.analyzer import analyze

    diff = _diff("app.py", ["def f():", "    return 1"]) + _diff("tests/test_app.py", ["def test_f():", "    pass"])
    report = analyze(_manifest(), diff, _spec(), ResourceUsage(peak_vram_mb=6000, vram_total_mb=12000))
    assert report.badge == "PASS"
    assert report.metrics["files_changed"] == 2
    assert report.metrics["lines_added"] == 4
    assert report.metrics["dominant_phase"] == "agent_and_verify"
    assert report.metrics["dominant_phase_pct"] == 90.0


def test_vram_threshold_boundary():
    from dark_factory.analysis.analyzer import analyze

    ok = analyze(_manifest(), "", _spec(), ResourceUsage(peak_vram_mb=10800, vram_total_mb=12000))
    assert not [f for f in ok.findings if f.category == "resources"]
    hot = analyze(_manifest(), "", _spec(), ResourceUsage(peak_vram_mb=10801, vram_total_mb=12000))
    assert [f for f in hot.findings if f.category == "resources" and f.severity == "WARN"]


def test_ram_threshold_and_unavailable_resources():
    from dark_factory.analysis.analyzer import analyze

    hot = analyze(_manifest(), "", _spec(), ResourceUsage(peak_ram_mb=28000, ram_total_mb=32000))
    assert [f for f in hot.findings if f.category == "resources" and "RAM" in f.summary]
    none = analyze(_manifest(), "", _spec(), ResourceUsage())
    assert not [f for f in none.findings if f.category == "resources"]


def test_slow_throughput_and_missing_telemetry():
    from dark_factory.analysis.analyzer import analyze

    slow = analyze(_manifest(tps=9.9), "", _spec(), ResourceUsage())
    assert [f for f in slow.findings if f.category == "performance" and "tok/s" in f.summary]
    edge = analyze(_manifest(tps=10.0), "", _spec(), ResourceUsage())
    assert not [f for f in edge.findings if "tok/s" in f.summary]
    m = _manifest()
    m.model_telemetry = None
    assert analyze(m, "", _spec(), ResourceUsage()).badge == "PASS"


def test_healing_exhausted_warns():
    from dark_factory.analysis.analyzer import analyze

    warn = analyze(_manifest(healing=3), "", _spec(3), ResourceUsage())
    assert [f for f in warn.findings if "healing" in f.summary.lower()]
    fine = analyze(_manifest(healing=2), "", _spec(3), ResourceUsage())
    assert not [f for f in fine.findings if "healing" in f.summary.lower()]


def test_function_complexity_and_length_from_sources():
    from dark_factory.analysis.analyzer import analyze

    branches = ["def busy(x):"] + [f"    if x == {i}:\n        return {i}" for i in range(11)] + ["    return -1"]
    src = "\n".join(branches) + "\n"
    diff = _diff("app.py", src.splitlines()) + _diff("tests/test_app.py", ["def test_a():", "    pass"])
    report = analyze(_manifest(), diff, _spec(), ResourceUsage(), sources={"app.py": src})
    quality = [f for f in report.findings if f.category == "quality" and "complexity" in f.summary]
    assert quality and "busy" in quality[0].summary
    assert report.metrics["max_complexity"] == 12

    long_src = "def long():\n" + "    x = 1\n" * 61
    report = analyze(
        _manifest(),
        _diff("app.py", long_src.splitlines()) + _diff("tests/test_app.py", ["def test_a(): pass"]),
        _spec(),
        ResourceUsage(),
        sources={"app.py": long_src},
    )
    assert [f for f in report.findings if "lines long" in f.summary]


def test_only_changed_functions_are_judged():
    from dark_factory.analysis.analyzer import analyze

    src = (
        "def busy(x):\n"
        + "".join(f"    if x == {i}:\n        return {i}\n" for i in range(12))
        + "\ndef small():\n    return 1\n"
    )
    last = len(src.splitlines())
    diff = _diff("app.py", ["    return 1"], start=last) + _diff("tests/test_a.py", ["x = 1"])
    report = analyze(_manifest(), diff, _spec(), ResourceUsage(), sources={"app.py": src})
    assert not [f for f in report.findings if "complexity" in f.summary]


def test_source_without_tests_warns_and_unparseable_is_skipped():
    from dark_factory.analysis.analyzer import analyze

    diff = _diff("pkg/mod.py", ["def broken(:"])
    report = analyze(_manifest(), diff, _spec(), ResourceUsage(), sources={"pkg/mod.py": "def broken(:\n"})
    assert [f for f in report.findings if f.category == "quality" and "tests" in f.summary]
    assert not [f for f in report.findings if "complexity" in f.summary]


def test_empty_diff_has_zero_metrics():
    from dark_factory.analysis.analyzer import analyze

    report = analyze(_manifest(), "", _spec(), ResourceUsage())
    assert report.metrics["files_changed"] == 0
    assert report.metrics["lines_added"] == 0
    assert report.metrics["lines_removed"] == 0


def test_parse_diff_content_lines_that_look_like_headers():
    from dark_factory.analysis.analyzer import parse_diff

    diff = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,2 +1,3 @@\n x\n--- sql comment\n+++ tests/test_x.py\n+y\n"
    added, removed = parse_diff(diff)
    assert set(added) == {"a.py"}
    assert added["a.py"] == {2, 3}
    assert removed == 1


def test_parse_diff_counts_deleted_files_renames_and_quoted_paths():
    from dark_factory.analysis.analyzer import parse_diff

    deleted = "diff --git a/old.py b/old.py\ndeleted file mode 100644\n--- a/old.py\n+++ /dev/null\n@@ -1,3 +0,0 @@\n-a\n-b\n-c\n"
    added, removed = parse_diff(deleted)
    assert "old.py" in added and removed == 3

    renamed = "diff --git a/o.py b/n.py\nsimilarity index 100%\nrename from o.py\nrename to n.py\n"
    assert "n.py" in parse_diff(renamed)[0]

    quoted = 'diff --git "a/q\\"x.py" "b/q\\"x.py"\n--- "a/q\\"x.py"\n+++ "b/q\\"x.py"\n@@ -0,0 +1 @@\n+z = 1\n'
    assert list(parse_diff(quoted)[0]) == ['q"x.py']


def test_collect_sources_skips_oversized_files():
    from dark_factory.analysis.analyzer import MAX_SOURCE_BYTES, collect_sources

    class FakeSandbox:
        def read_file(self, path):
            return b"x = 1\n" * (MAX_SOURCE_BYTES // 4) if path == "big.py" else b"y = 2\n"

    diff = _diff("big.py", ["x = 1"]) + _diff("small.py", ["y = 2"])
    assert set(collect_sources(FakeSandbox(), diff)) == {"small.py"}
