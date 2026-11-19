"""tests/unit/test_parallel_batch.py - Orden, admision, cancelacion y limites."""

import asyncio
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from src.application.document_errors import InvalidDocument
from src.application.dtos.document_dtos import Document, DocumentUpload, ProposedVehicleFields
from src.application.use_cases.process_batch_documents import ProcessBatchDocumentsUseCase
from src.infrastructure.batch_processing import BatchDocumentProcessor
from src.infrastructure.settings import config


def test_parallel_use_case_keeps_input_order_and_does_not_eagerly_consume_uploads():
    async def run():
        gate = asyncio.Event()
        active, peak, consumed = 0, 0, []

        def uploads():
            for index in range(12):
                consumed.append(index)
                yield DocumentUpload(BytesIO(b"pdf"), f"{index}.pdf")

        def save(source, name):
            return Document(name, name, name, "application/pdf", len(source.read()))

        async def extract(document):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await gate.wait()
            await asyncio.sleep(0.001 if document.id_documento == "0.pdf" else 0)
            active -= 1
            if document.id_documento == "3.pdf":
                raise InvalidDocument("PDF invalido")
            return ProposedVehicleFields(document.id_documento, patente="AB123CD")

        case = ProcessBatchDocumentsUseCase(save, Mock(), process_saved=extract, parallelism=2)
        task = asyncio.create_task(case.execute(uploads()))
        for _ in range(1000):
            if active == 2:
                break
            await asyncio.sleep(0.001)
        assert active == 2 and consumed == [0, 1]
        gate.set()
        results = await asyncio.wait_for(task, 5)
        assert peak == 2
        assert [r.nombre_original for r in results] == [f"{i}.pdf" for i in range(12)]
        assert [r.id_documento for r in results] == [f"{i}.pdf" for i in range(12)]
        assert results[3].fallo and results[3].error == "PDF invalido"
        assert all(not r.fallo for i, r in enumerate(results) if i != 3)

    asyncio.run(run())


def test_cancelled_batch_drains_inflight_uploads_without_starting_more():
    async def run():
        started, finish = asyncio.Event(), asyncio.Event()
        consumed = []

        def save(source, name):
            consumed.append(name)
            return Document(name, name, name, "application/pdf", 3)

        async def extract(document):
            started.set()
            await finish.wait()
            return ProposedVehicleFields(document.id_documento)

        case = ProcessBatchDocumentsUseCase(save, Mock(), process_saved=extract)
        task = asyncio.create_task(
            case.execute(
                [
                    DocumentUpload(BytesIO(b"pdf"), "first.pdf"),
                    DocumentUpload(BytesIO(b"pdf"), "second.pdf"),
                ]
            )
        )
        await asyncio.wait_for(started.wait(), 5)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        finish.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert consumed == ["first.pdf"]

    asyncio.run(run())


def test_parallel_completion_stores_pending_in_input_order_and_continues_after_storage_error():
    async def run():
        last_finished = asyncio.Event()
        stored, finished = [], []

        def save(source, name):
            return Document(name, name, name, "application/pdf", 3)

        async def extract(document):
            if document.id_documento == "first.pdf":
                await last_finished.wait()
            elif document.id_documento == "broken.pdf":
                last_finished.set()
            finished.append(document.id_documento)
            return ProposedVehicleFields(document.id_documento, patente="AB123CD")

        def persist(document):
            stored.append(document.id_documento)
            if document.id_documento == "broken.pdf":
                raise RuntimeError("synthetic storage failure")

        names = ["first.pdf", "broken.pdf", "last.pdf"]
        case = ProcessBatchDocumentsUseCase(
            save, Mock(), process_saved=extract, parallelism=3, save_pending=persist
        )
        results = await asyncio.wait_for(
            case.execute([DocumentUpload(BytesIO(b"pdf"), name) for name in names]), 5
        )
        assert finished.index("broken.pdf") < finished.index("first.pdf")
        assert stored == names
        assert [r.nombre_original for r in results] == names
        assert [r.fallo for r in results] == [False, True, False]
        assert results[1].id_documento == "broken.pdf" and results[1].patente is None
        assert results[1].requiere_revision is False

    asyncio.run(run())


@pytest.mark.parametrize(
    "cpus,affinity,expected", [(None, 1, 1), (1, 1, 1), (2, 2, 1), (8, 3, 2), (32, 32, 4)]
)
def test_cpu_reservation_and_affinity(monkeypatch, cpus, affinity, expected):
    monkeypatch.setattr(
        config,
        "os",
        SimpleNamespace(cpu_count=lambda: cpus, sched_getaffinity=lambda _: set(range(affinity))),
    )
    assert config.batch_cpu_limit() == expected


def test_process_cpu_count_and_affinity_failure(monkeypatch):
    def unavailable(_):
        raise OSError("affinity unavailable")

    monkeypatch.setattr(
        config,
        "os",
        SimpleNamespace(
            cpu_count=lambda: 16, process_cpu_count=lambda: 2, sched_getaffinity=unavailable
        ),
    )
    assert config.batch_cpu_limit() == 1


@pytest.mark.parametrize("budget,workers", [(256, 1), (512, 2), (1024, 4), (4096, 4)])
def test_worker_memory_reservation_limits_pool(monkeypatch, budget, workers):
    monkeypatch.setattr("src.infrastructure.batch_processing.batch_cpu_limit", lambda: 4)
    processor = BatchDocumentProcessor(
        config.Settings(BATCH_MAX_WORKERS=4, BATCH_MEMORY_BUDGET_MB=budget)
    )
    assert processor.max_workers == workers
    assert processor._pool is None
    asyncio.run(processor.close())


@pytest.mark.parametrize(
    "values", [{"BATCH_MAX_WORKERS": 0}, {"BATCH_MAX_WORKERS": 5}, {"BATCH_MEMORY_BUDGET_MB": 255}]
)
def test_invalid_resource_configuration_rejected(values):
    with pytest.raises(ValidationError):
        config.Settings(**values)
    with pytest.raises(ValueError):
        ProcessBatchDocumentsUseCase(Mock(), Mock(), parallelism=0)
