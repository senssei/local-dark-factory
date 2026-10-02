"""Unit tests for dark_factory.analysis.resources."""

import subprocess
import time
from types import SimpleNamespace


def test_read_gpu_parses_nvidia_smi(monkeypatch):
    from dark_factory.analysis import resources

    seen = {}

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        return SimpleNamespace(stdout="11500, 12227, 83\n", returncode=0)

    monkeypatch.setattr(resources.shutil, "which", lambda name: "/usr/bin/nvidia-smi")
    monkeypatch.setattr(resources.subprocess, "run", fake_run)
    assert resources.read_gpu() == (11500.0, 12227.0, 83.0)
    assert isinstance(seen["argv"], list) and seen["argv"][0] == "nvidia-smi"


def test_read_gpu_unavailable_returns_none(monkeypatch):
    from dark_factory.analysis import resources

    monkeypatch.setattr(resources.shutil, "which", lambda name: None)
    assert resources.read_gpu() is None

    monkeypatch.setattr(resources.shutil, "which", lambda name: "/usr/bin/nvidia-smi")

    def boom(*a, **k):
        raise subprocess.CalledProcessError(1, "nvidia-smi")

    monkeypatch.setattr(resources.subprocess, "run", boom)
    assert resources.read_gpu() is None

    monkeypatch.setattr(resources.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout="garbage", returncode=0))
    assert resources.read_gpu() is None


def test_read_ram_parses_meminfo(tmp_path):
    from dark_factory.analysis import resources

    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal:       32768000 kB\nMemFree: 100 kB\nMemAvailable:   16384000 kB\n")
    used, total = resources.read_ram(meminfo)
    assert total == 32000.0
    assert used == 16000.0
    assert resources.read_ram(tmp_path / "missing") is None


def test_sampler_records_peaks_and_stops_idempotently(monkeypatch):
    from dark_factory.analysis import resources

    readings = iter([(1000.0, 12000.0, 10.0), (9000.0, 12000.0, 90.0)] + [(2000.0, 12000.0, 20.0)] * 1000)
    monkeypatch.setattr(resources, "read_gpu", lambda: next(readings))
    monkeypatch.setattr(resources, "read_ram", lambda path=None: (8000.0, 32000.0))

    with resources.ResourceSampler(interval_sec=0.01) as sampler:
        time.sleep(0.15)
    usage = sampler.usage()
    sampler.stop()
    sampler.stop()
    assert usage.samples >= 2
    assert usage.peak_vram_mb == 9000.0
    assert usage.vram_total_mb == 12000.0
    assert usage.peak_ram_mb == 8000.0
    assert usage.avg_gpu_util_pct is not None and usage.avg_gpu_util_pct > 10.0


def test_sampler_unavailable_sources_yield_none_fields(monkeypatch):
    from dark_factory.analysis import resources

    monkeypatch.setattr(resources, "read_gpu", lambda: None)
    monkeypatch.setattr(resources, "read_ram", lambda path=None: None)
    with resources.ResourceSampler(interval_sec=0.01) as sampler:
        time.sleep(0.05)
    usage = sampler.usage()
    assert usage.peak_vram_mb is None and usage.peak_ram_mb is None
    assert usage.avg_gpu_util_pct is None


def test_sampler_never_raises_when_reader_fails(monkeypatch):
    from dark_factory.analysis import resources

    def boom():
        raise RuntimeError("driver exploded")

    monkeypatch.setattr(resources, "read_gpu", boom)
    monkeypatch.setattr(resources, "read_ram", lambda path=None: (1.0, 2.0))
    with resources.ResourceSampler(interval_sec=0.01) as sampler:
        time.sleep(0.05)
    assert sampler.usage().peak_ram_mb == 1.0
