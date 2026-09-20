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

    loaded_patch = locker.load_patch("run-test-storage-01")
    assert loaded_patch == diff

    # List runs
    all_runs = locker.list_runs()
    assert len(all_runs) == 1
    assert all_runs[0].run_id == "run-test-storage-01"
