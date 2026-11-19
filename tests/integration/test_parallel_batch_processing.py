"""tests/integration/test_parallel_batch_processing.py - Spawn y degradacion reales."""

import asyncio
import json
import os
import time
from concurrent.futures import Future
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path
from threading import Event, Lock
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from src.application.document_errors import InvalidDocument
from src.application.dtos.document_dtos import Document, ExtractedText
from src.infrastructure import batch_processing as batch
from src.infrastructure.persistence import local_document_storage as storage
from src.infrastructure.settings.config import Settings, get_settings
from src.main import create_app
from tests.test_documents import make_pdf


def process_probe(job):
    """Importable bajo spawn: mide solapamiento sin pasar recursos del padre."""
    start = time.monotonic()
    # Rendezvous de los dos hijos: no depender del tiempo relativo de arranque.
    directory = Path(job.path).parent
    (directory / f"{os.getpid()}.ready").touch()
    deadline = start + 15
    while len(list(directory.glob("*.ready"))) < 2:
        if time.monotonic() > deadline:
            raise RuntimeError("No iniciaron ambos procesos spawn")
        time.sleep(0.005)
    time.sleep(0.15)
    trace = {
        "pid": os.getpid(),
        "start": start,
        "end": time.monotonic(),
        "omp": os.environ.get("OMP_THREAD_LIMIT"),
    }
    Path(job.path + ".trace").write_text(json.dumps(trace), encoding="utf-8")
    return ExtractedText(
        job.document.id_documento, job.document.nombre_original, "Dominio: AB123CD", 16, False, "ok"
    )


@pytest.fixture
def processor(monkeypatch):
    monkeypatch.setattr(batch, "batch_cpu_limit", lambda: 4)
    value = batch.BatchDocumentProcessor(Settings(BATCH_MAX_WORKERS=2))
    yield value
    asyncio.run(value.close())


def job_document(tmp_path, name="native.pdf"):
    path = tmp_path / name
    path.write_bytes(make_pdf("Dominio: AB123CD"))
    return Document(name, name, name, "application/pdf", path.stat().st_size), path


def test_real_spawn_pool_reuses_two_processes_and_limits_all_batches(
    processor, tmp_path, monkeypatch
):
    monkeypatch.setattr(batch, "extract_batch_text", process_probe)
    inputs = [job_document(tmp_path, f"{i}.pdf") for i in range(8)]

    async def run():
        # Dos solicitudes comparten la admision del mismo pool.
        return await asyncio.gather(*[processor.extract(*item) for item in inputs])

    results = asyncio.run(run())
    traces = [json.loads(Path(str(path) + ".trace").read_text()) for _, path in inputs]
    assert len({t["pid"] for t in traces}) == 2
    assert all(t["pid"] != os.getpid() and t["omp"] == "1" for t in traces)
    assert [r.id_documento for r in results] == [d.id_documento for d, _ in inputs]
    events = sorted([(t["start"], 1) for t in traces] + [(t["end"], -1) for t in traces])
    active, peak = 0, 0
    for _, delta in events:
        active += delta
        peak = max(peak, active)
    assert peak == 2
    children = list(processor._pool._processes.values())
    asyncio.run(processor.close())
    assert all(not child.is_alive() for child in children)
    with pytest.raises(RuntimeError, match="cerrado"):
        asyncio.run(processor.extract(*inputs[0]))


def test_spawn_extracts_native_pdf_and_propagates_document_error(processor, tmp_path):
    document, path = job_document(tmp_path)

    async def run():
        result = await processor.extract(document, path)
        assert "AB123CD" in result.texto_extraido
        path.write_bytes(b"not pdf")
        with pytest.raises(InvalidDocument):
            await processor.extract(document, path)
        path.write_bytes(make_pdf("Dominio: XY123ZZ"))
        assert "XY123ZZ" in (await processor.extract(document, path)).texto_extraido
        assert processor._failed is False

    asyncio.run(run())


def test_pool_start_failure_falls_back_without_changing_original(
    processor, tmp_path, monkeypatch, caplog
):
    monkeypatch.setattr(
        batch, "ProcessPoolExecutor", Mock(side_effect=OSError("spawn unavailable"))
    )
    document, path = job_document(tmp_path)
    original = path.read_bytes()
    result = asyncio.run(processor.extract(document, path))
    assert "AB123CD" in result.texto_extraido
    assert processor._failed and path.read_bytes() == original
    assert "fallback secuencial" in caplog.text


def test_broken_pool_fallback_is_serial_across_jobs(processor, tmp_path, monkeypatch):
    fake = Mock()

    def submit(*args):
        future = Future()
        future.set_exception(BrokenProcessPool("synthetic worker failure"))
        return future

    fake.submit.side_effect = submit
    monkeypatch.setattr(batch, "ProcessPoolExecutor", Mock(return_value=fake))
    active, peak = 0, 0
    lock = Lock()
    original = batch.extract_batch_text

    def extract(job):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        try:
            time.sleep(0.02)
            return original(job)
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(batch, "extract_batch_text", extract)
    inputs = [job_document(tmp_path, f"{i}.pdf") for i in range(4)]

    async def run():
        return await asyncio.gather(*[processor.extract(*item) for item in inputs])

    assert all("AB123CD" in r.texto_extraido for r in asyncio.run(run()))
    assert peak == 1 and processor._failed


def test_single_worker_cancellation_keeps_admission_until_extraction_finishes(
    tmp_path, monkeypatch
):
    processor = batch.BatchDocumentProcessor(Settings(BATCH_MAX_WORKERS=1))
    started, finish = Event(), Event()
    calls = []
    original = batch.extract_batch_text

    def extract(job):
        calls.append(job.document.id_documento)
        if len(calls) == 1:
            started.set()
            assert finish.wait(10)
        return original(job)

    monkeypatch.setattr(batch, "extract_batch_text", extract)
    first, second = job_document(tmp_path, "first.pdf"), job_document(tmp_path, "second.pdf")

    async def run():
        task = asyncio.create_task(processor.extract(*first))
        assert await asyncio.to_thread(started.wait, 5)
        task.cancel()
        waiting = asyncio.create_task(processor.extract(*second))
        await asyncio.sleep(0.01)
        assert not task.done() and not waiting.done() and calls == ["first.pdf"]
        finish.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert "AB123CD" in (await waiting).texto_extraido
        await processor.close()

    try:
        asyncio.run(run())
    finally:
        finish.set()
    assert processor._pool is None and calls == ["first.pdf", "second.pdf"]


@pytest.mark.parametrize("fallback", [False, True])
def test_http_parallel_batch_order_failures_persistence_and_no_automatic_confirmation(
    tmp_path, monkeypatch, fallback
):
    monkeypatch.setattr(batch, "batch_cpu_limit", lambda: 4)
    monkeypatch.setattr(storage, "UPLOAD_DIRECTORY", tmp_path / "uploads")
    settings = get_settings()
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{(tmp_path / 'api.db').as_posix()}")
    monkeypatch.setattr(settings, "BATCH_MAX_WORKERS", 2)
    if fallback:
        monkeypatch.setattr(
            batch, "ProcessPoolExecutor", Mock(side_effect=OSError("spawn unavailable"))
        )
    files = [
        ("files", (name, content))
        for name, content in [
            ("one.pdf", make_pdf("Dominio: AB123CD")),
            ("broken.pdf", b"not a PDF"),
            ("last.pdf", make_pdf("Dominio: XY123ZZ")),
        ]
    ]
    app = create_app()
    with TestClient(app) as client:
        response = client.post("/api/v1/documents/batch", files=files)
        assert response.status_code == 200
        results = response.json()
        assert [r["nombre_original"] for r in results] == ["one.pdf", "broken.pdf", "last.pdf"]
        assert [r["fallo"] for r in results] == [False, True, False]
        assert all(r["id_documento"] for r in results)
        assert [r["patente"] for r in results] == ["AB123CD", None, "XY123ZZ"]
        documents = client.get("/api/v1/documents").json()
        assert [d["nombre_original"] for d in documents] == ["one.pdf", "last.pdf"]
        assert {d["id_documento"] for d in documents} == {
            results[0]["id_documento"],
            results[2]["id_documento"],
        }
        assert all(d["estado"] == "pendiente" for d in documents)
        assert len(client.get("/api/v1/history").json()) == 2
        assert client.get("/api/v1/vehicles").json() == []
        assert (app.state.batch_processor._pool is None) is fallback
        assert app.state.batch_processor._failed is fallback
        assert len(list(storage.UPLOAD_DIRECTORY.glob("*.json"))) == 3
        with app.state.sqlite_connections.connection() as connection:
            assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
