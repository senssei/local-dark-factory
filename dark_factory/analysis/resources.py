"""Host resource sampling (GPU VRAM/utilization, RAM) during a run. Stdlib only, never raises into the run."""

from __future__ import annotations

import shutil
import subprocess
import threading
from pathlib import Path
from types import TracebackType

from dark_factory.domain.types import ResourceUsage

_MEMINFO = Path("/proc/meminfo")


def read_gpu() -> tuple[float, float, float] | None:
    """Return (used MiB, total MiB, utilization %) of the first GPU, or None when unavailable."""
    if not shutil.which("nvidia-smi"):
        return None
    try:
        res = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used,memory.total,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        used, total, util = (float(part) for part in res.stdout.splitlines()[0].split(","))
        return used, total, util
    except Exception:
        return None


def read_ram(path: Path | None = None) -> tuple[float, float] | None:
    """Return (used MiB, total MiB) of host RAM from /proc/meminfo, or None when unavailable."""
    try:
        values: dict[str, float] = {}
        for line in (path or _MEMINFO).read_text(encoding="utf-8").splitlines():
            key, _, rest = line.partition(":")
            values[key] = float(rest.split()[0])
        total = values["MemTotal"] / 1024
        return total - values["MemAvailable"] / 1024, total
    except Exception:
        return None


class ResourceSampler:
    """Samples host resources on a daemon thread; use as a context manager around a run phase."""

    def __init__(self, interval_sec: float = 2.0) -> None:
        self.interval_sec = interval_sec
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._samples = 0
        self._peak_vram: float | None = None
        self._vram_total: float | None = None
        self._util_sum = 0.0
        self._util_count = 0
        self._peak_ram: float | None = None
        self._ram_total: float | None = None

    def __enter__(self) -> ResourceSampler:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.stop()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, name="resource-sampler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Idempotent: stop the thread and wait for it."""
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=self.interval_sec + 6)

    def _loop(self) -> None:
        while True:
            try:
                self._sample()
            except Exception:
                pass
            if self._stop.wait(self.interval_sec):
                return

    def _sample(self) -> None:
        gpu = None
        try:
            gpu = read_gpu()
        except Exception:
            pass
        ram = read_ram()
        with self._lock:
            self._samples += 1
            if gpu is not None:
                used, total, util = gpu
                self._peak_vram = used if self._peak_vram is None else max(self._peak_vram, used)
                self._vram_total = total
                self._util_sum += util
                self._util_count += 1
            if ram is not None:
                used, total = ram
                self._peak_ram = used if self._peak_ram is None else max(self._peak_ram, used)
                self._ram_total = total

    def usage(self) -> ResourceUsage:
        with self._lock:
            return ResourceUsage(
                peak_vram_mb=self._peak_vram,
                vram_total_mb=self._vram_total,
                avg_gpu_util_pct=round(self._util_sum / self._util_count, 1) if self._util_count else None,
                peak_ram_mb=self._peak_ram,
                ram_total_mb=self._ram_total,
                samples=self._samples,
            )
