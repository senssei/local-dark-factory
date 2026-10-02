"""Unit tests for EvidenceLocker."""

from pathlib import Path

from dark_factory.domain.types import (
    EvidenceManifest,
    ModelTelemetry,
    RunStatus,
    StepExecution,
)
from dark_factory.storage import EvidenceLocker


def test_evidence_locker_save_and_load(tmp_path: Path):
    locker = EvidenceLocker(storage_dir=tmp_path)

    manifest = EvidenceManifest.create(
        run_id="run-test-storage-01",
        repo_path="/tmp/fake_repo",
        base_rev="abc1234",
    )
    manifest.status = RunStatus.AWAITING_REVIEW
    manifest.verification_results = [
        StepExecution("test", 0, "All passed", "", 1.2),
    ]
    manifest.model_telemetry = ModelTelemetry(
        engine="ollama",
        model_name="qwen2.5-coder:14b",
        prompt_tokens=100,
        completion_tokens=200,
        total_tokens=300,
        tokens_per_sec=35.5,
    )
    manifest.repeated_failure_streak = 2

    diff = "--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new\n"
    transcript = "=== Transcript ===\nStep test: PASSED\n"

    locker.save_run(manifest, patch_content=diff, transcript=transcript)

    # Reload
    loaded = locker.load_manifest("run-test-storage-01")
    assert loaded.run_id == "run-test-storage-01"
    assert loaded.status == RunStatus.AWAITING_REVIEW
    assert loaded.patch_size_bytes == len(diff.encode("utf-8"))
    assert loaded.model_telemetry.tokens_per_sec == 35.5
    assert len(loaded.verification_results) == 1
    assert loaded.repeated_failure_streak == 2

    loaded_patch = locker.load_patch("run-test-storage-01")
    assert loaded_patch == diff

    # List runs
    all_runs = locker.list_runs()
    assert len(all_runs) == 1
    assert all_runs[0].run_id == "run-test-storage-01"


def test_load_manifest_defaults_repeated_failure_streak_for_old_manifests(tmp_path: Path):
    """A manifest.json written before this field existed must still load cleanly."""
    import json

    locker = EvidenceLocker(storage_dir=tmp_path)
    run_dir = tmp_path / "runs" / "run-legacy"
    run_dir.mkdir(parents=True)
    (run_dir / "diff.patch").write_text("")
    legacy_manifest = {
        "run_id": "run-legacy",
        "status": "AWAITING_REVIEW",
        "repo_path": "/tmp/fake_repo",
        "base_rev": "abc1234",
        "created_at": "2026-01-01T00:00:00+00:00",
        "healing_attempts": 0,
        "verification_results": [],
        # no "repeated_failure_streak" key at all, matching a pre-Phase-12 manifest
    }
    (run_dir / "manifest.json").write_text(json.dumps(legacy_manifest))

    loaded = locker.load_manifest("run-legacy")
    assert loaded.repeated_failure_streak == 0


def test_evidence_locker_saves_and_loads_adversarial_report(tmp_path: Path):
    from dark_factory.domain import AdversarialFinding, AdversarialReport

    locker = EvidenceLocker(storage_dir=tmp_path)
    manifest = EvidenceManifest.create(
        run_id="run-adv-storage",
        repo_path="/tmp/fake_repo",
        base_rev="abc1234",
    )
    finding = AdversarialFinding(
        severity="CRITICAL",
        category="security",
        summary="Path traversal detected",
        details="Relative path can escape sandbox",
    )
    report = AdversarialReport(
        passed=False,
        summary="Critical security defect detected",
        findings=[finding],
    )
    manifest.adversarial_report = report

    run_folder = locker.save_run(manifest, patch_content="diff")
    adv_file = run_folder / "adversarial.md"
    assert adv_file.exists()
    adv_text = adv_file.read_text(encoding="utf-8")
    assert "Path traversal detected" in adv_text
    assert "CRITICAL" in adv_text

    loaded = locker.load_manifest("run-adv-storage")
    assert loaded.adversarial_report is not None
    assert loaded.adversarial_report.summary == "Critical security defect detected"
    assert loaded.adversarial_report.findings[0].category == "security"


def test_load_manifest_defaults_adversarial_report_for_old_manifests(tmp_path: Path):
    import json

    locker = EvidenceLocker(storage_dir=tmp_path)
    run_dir = tmp_path / "runs" / "run-no-adv"
    run_dir.mkdir(parents=True)
    (run_dir / "diff.patch").write_text("")
    legacy_manifest = {
        "run_id": "run-no-adv",
        "status": "AWAITING_REVIEW",
        "repo_path": "/tmp/fake_repo",
        "base_rev": "abc1234",
        "created_at": "2026-01-01T00:00:00+00:00",
        "healing_attempts": 0,
        "verification_results": [],
    }
    (run_dir / "manifest.json").write_text(json.dumps(legacy_manifest))

    loaded = locker.load_manifest("run-no-adv")
    assert loaded.adversarial_report is None


def test_evidence_locker_saves_and_loads_execution_plan(tmp_path: Path):
    from dark_factory.domain.types import ExecutionPlan

    locker = EvidenceLocker(storage_dir=tmp_path)
    manifest = EvidenceManifest.create(run_id="run-plan-storage", repo_path="/tmp/fake_repo", base_rev="abc1234")
    manifest.status = RunStatus.AWAITING_REVIEW
    plan = ExecutionPlan(
        plan_id="plan-storage-01",
        summary="Introduce modular caching layer",
        invariants=["TTL expiry must be deterministic", "LRU cache size capped at 1000 items"],
        steps=["1. Implement MemoryCache", "2. Connect cache decorator to repo"],
        target_files=["cache.py", "repository.py"],
        raw_plan="Detailed execution plan with rationale",
    )
    manifest.execution_plan = plan

    run_folder = locker.save_run(manifest, patch_content="diff")
    plan_file = run_folder / "plan.md"
    assert plan_file.exists()
    plan_text = plan_file.read_text(encoding="utf-8")
    assert "Introduce modular caching layer" in plan_text
    assert "TTL expiry must be deterministic" in plan_text
    assert "1. Implement MemoryCache" in plan_text

    loaded = locker.load_manifest("run-plan-storage")
    assert loaded.execution_plan is not None
    assert loaded.execution_plan.plan_id == "plan-storage-01"
    assert loaded.execution_plan.summary == "Introduce modular caching layer"
    assert len(loaded.execution_plan.invariants) == 2
    assert loaded.execution_plan.target_files == ["cache.py", "repository.py"]


def test_load_manifest_defaults_execution_plan_for_old_manifests(tmp_path: Path):
    import json

    locker = EvidenceLocker(storage_dir=tmp_path)
    run_dir = tmp_path / "runs" / "run-no-plan"
    run_dir.mkdir(parents=True)
    (run_dir / "diff.patch").write_text("")
    legacy_manifest = {
        "run_id": "run-no-plan",
        "status": "AWAITING_REVIEW",
        "repo_path": "/tmp/fake_repo",
        "base_rev": "abc1234",
        "created_at": "2026-01-01T00:00:00+00:00",
        "healing_attempts": 0,
        "verification_results": [],
    }
    (run_dir / "manifest.json").write_text(json.dumps(legacy_manifest))

    loaded = locker.load_manifest("run-no-plan")
    assert loaded.execution_plan is None


def test_evidence_locker_saves_and_loads_adversarial_test_code(tmp_path: Path):
    locker = EvidenceLocker(storage_dir=tmp_path)
    manifest = EvidenceManifest.create(run_id="run-mut-storage", repo_path="/tmp/fake_repo", base_rev="abc1234")
    manifest.status = RunStatus.AWAITING_REVIEW
    manifest.adversarial_test_code = "def test_adversarial_boundary():\n    assert True\n"

    run_folder = locker.save_run(manifest, patch_content="diff")
    test_file = run_folder / "adversarial_test.py"
    assert test_file.exists()
    assert test_file.read_text(encoding="utf-8") == "def test_adversarial_boundary():\n    assert True\n"

    loaded = locker.load_manifest("run-mut-storage")
    assert loaded.adversarial_test_code == "def test_adversarial_boundary():\n    assert True\n"


def test_load_manifest_defaults_adversarial_test_code_for_old_manifests(tmp_path: Path):
    import json

    locker = EvidenceLocker(storage_dir=tmp_path)
    run_dir = tmp_path / "runs" / "run-no-mut"
    run_dir.mkdir(parents=True)
    (run_dir / "diff.patch").write_text("")
    legacy_manifest = {
        "run_id": "run-no-mut",
        "status": "AWAITING_REVIEW",
        "repo_path": "/tmp/fake_repo",
        "base_rev": "abc1234",
        "created_at": "2026-01-01T00:00:00+00:00",
        "healing_attempts": 0,
        "verification_results": [],
    }
    (run_dir / "manifest.json").write_text(json.dumps(legacy_manifest))

    loaded = locker.load_manifest("run-no-mut")
    assert loaded.adversarial_test_code is None


def test_evidence_locker_saves_and_loads_analysis_report(tmp_path: Path):
    from dark_factory.domain.types import AnalysisFinding, AnalysisReport, ResourceUsage

    locker = EvidenceLocker(storage_dir=tmp_path)
    manifest = EvidenceManifest.create(run_id="run-an-storage", repo_path="/tmp/fake_repo", base_rev="abc1234")
    manifest.analysis_report = AnalysisReport(
        summary="VRAM tight",
        resources=ResourceUsage(peak_vram_mb=11500, vram_total_mb=12227, samples=7),
        findings=[AnalysisFinding("WARN", "resources", "Peak VRAM 94%", "11500/12227 MiB")],
        metrics={"files_changed": 2, "dominant_phase": "agent_and_verify"},
    )

    run_folder = locker.save_run(manifest, patch_content="diff")
    text = (run_folder / "analysis.md").read_text(encoding="utf-8")
    assert "Peak VRAM 94%" in text and "11500" in text

    loaded = locker.load_manifest("run-an-storage")
    assert loaded.analysis_report is not None
    assert loaded.analysis_report.resources.peak_vram_mb == 11500
    assert loaded.analysis_report.resources.avg_gpu_util_pct is None
    assert loaded.analysis_report.findings[0].category == "resources"
    assert loaded.analysis_report.metrics["files_changed"] == 2


def test_load_manifest_defaults_analysis_report_for_old_manifests(tmp_path: Path):
    import json

    locker = EvidenceLocker(storage_dir=tmp_path)
    run_dir = tmp_path / "runs" / "run-no-an"
    run_dir.mkdir(parents=True)
    legacy = {
        "run_id": "run-no-an",
        "status": "AWAITING_REVIEW",
        "repo_path": "/tmp/fake_repo",
        "base_rev": "abc1234",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    (run_dir / "manifest.json").write_text(json.dumps(legacy))
    assert locker.load_manifest("run-no-an").analysis_report is None
