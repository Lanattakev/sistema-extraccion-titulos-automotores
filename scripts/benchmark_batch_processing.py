"""scripts/benchmark_batch_processing.py - Benchmark local con OCR real y datos sinteticos."""

import argparse
import ctypes
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from src.infrastructure.persistence import local_document_storage as storage
from src.infrastructure.settings.config import batch_cpu_limit, get_settings
from src.main import create_app


def windows_peak_mib(pid: int) -> float | None:
    if sys.platform != "win32":
        return None
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
            (name, ctypes.c_size_t)
            for name in (
                "peak",
                "working",
                "peak_paged",
                "paged",
                "peak_nonpaged",
                "nonpaged",
                "pagefile",
                "peak_pagefile",
            )
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    api = ctypes.WinDLL("psapi", use_last_error=True)
    api.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    handle = kernel.OpenProcess(0x0400 | 0x0010, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        values = Counters()
        values.cb = ctypes.sizeof(values)
        if not api.GetProcessMemoryInfo(handle, ctypes.byref(values), values.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return round(values.peak / (1024 * 1024), 2)
    finally:
        kernel.CloseHandle(handle)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents", type=int, default=6)
    parser.add_argument("--pages", type=int, default=2)
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--workers", type=int, default=batch_cpu_limit())
    args = parser.parse_args()
    if min(args.documents, args.pages, args.repeat, args.workers) < 1 or args.documents > 100:
        parser.error("Valores positivos; hasta 100 documentos por lote.")
    root = Path(__file__).resolve().parents[1]
    scratch = Path(tempfile.mkdtemp(prefix="batch-benchmark-", dir=root / ".venv"))
    source = scratch / "synthetic.pdf"
    text = "Dominio: AB123CD\nMarca: TOYOTA\nModelo: COROLLA\nMotor: M1234567\nChasis: C123456789\nAnio: 2020"
    with Image.new("RGB", (1700, 2200), "white") as image:
        draw = ImageDraw.Draw(image)
        draw.multiline_text(
            (80, 80), text, fill="black", font=ImageFont.load_default(size=48), spacing=25
        )
        image.save(
            source, "PDF", resolution=150, save_all=True, append_images=[image] * (args.pages - 1)
        )
    content = source.read_bytes()
    files = [("files", (f"titulo-{index}.pdf", content)) for index in range(args.documents)]
    settings = get_settings()
    results = []
    for requested in (1, args.workers):
        directory = scratch / f"workers-{requested}"
        directory.mkdir()
        with (
            patch.object(
                settings, "DATABASE_URL", f"sqlite:///{(directory / 'audit.db').as_posix()}"
            ),
            patch.object(settings, "BATCH_MAX_WORKERS", requested),
            patch.object(storage, "UPLOAD_DIRECTORY", directory / "uploads"),
            TestClient(create_app()) as client,
        ):
            app = client.app
            processor = app.state.batch_processor
            times = []
            for _ in range(args.repeat + 1):
                start = time.perf_counter()
                response = client.post("/api/v1/documents/batch", files=files)
                times.append(time.perf_counter() - start)
                response.raise_for_status()
                batch = response.json()
                assert [item["nombre_original"] for item in batch] == [
                    entry[1][0] for entry in files
                ]
                assert all(not item["fallo"] and item["patente"] == "AB123CD" for item in batch), (
                    batch
                )
                assert processor._failed is False, "Un fallback no acredita rendimiento paralelo"
            pool = processor._pool
            children = list(pool._processes.values()) if pool is not None else []
            results.append(
                {
                    "requested": requested,
                    "effective_workers": processor.max_workers,
                    "cold_seconds": times[0],
                    "warm_seconds": times[1:],
                    "warm_median": statistics.median(times[1:]),
                    "parent_peak_mib": windows_peak_mib(os.getpid()),
                    "children_peak_mib": [windows_peak_mib(child.pid) for child in children],
                }
            )
            assert client.get("/api/v1/vehicles").json() == []
            with app.state.sqlite_connections.connection() as connection:
                assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    report = {
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "python": sys.version,
        "cpu_count": os.cpu_count(),
        "cpu_guard": batch_cpu_limit(),
        "documents": args.documents,
        "pages_each": args.pages,
        "results": results,
        "warm_speedup": results[0]["warm_median"] / results[1]["warm_median"],
        "artifacts": str(scratch),
        "note": "OCR real sintetico; no representa precision real ni carga sostenida. Picos Windows por proceso, no suma simultanea ni limite RSS.",
    }
    destination = scratch / "results.json"
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
