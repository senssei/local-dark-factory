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
