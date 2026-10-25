"""tests/integration/test_sqlite_history_repository.py"""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier

import pytest

from src.domain.document_record import DocumentRecord
from src.domain.vehicle_record import VehicleRecord
from src.infrastructure.persistence.sqlite_document_repository import (
    DocumentConflictError,
    SQLiteDocumentRepository,
)
from src.infrastructure.persistence.sqlite_vehicle_repository import SQLiteVehicleRepository


@pytest.fixture
def repositories(tmp_path):
    path = tmp_path / "history.db"
    vehicles = SQLiteVehicleRepository(path)
    documents = SQLiteDocumentRepository(path)
    return path, vehicles, documents


def reject_history_event(path, event_type):
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(f"""
            CREATE TRIGGER fail_history BEFORE INSERT ON history_events
            WHEN NEW.tipo_evento = '{event_type}'
            BEGIN SELECT RAISE(ABORT, 'history storage failure'); END
        """)


@pytest.mark.parametrize("event_type", ["documento_cargado", "documento_revisado", "documento_registrado"])
def test_history_failure_rolls_back_the_whole_operation(repositories, event_type):
    path, vehicles, documents = repositories
    vehicle = VehicleRecord("AB123CD", "Toyota", "Corolla", "M1", "C1", 2020)
    if event_type != "documento_cargado":
        documents.save_pending(DocumentRecord("doc-1", "titulo.pdf"))
    if event_type == "documento_registrado":
        documents.review("doc-1", vehicle)
    before_documents = documents.list_all()
    before_events = documents.history_repository.list_all()
    reject_history_event(path, event_type)
    with pytest.raises(sqlite3.IntegrityError, match="history storage failure"):
        if event_type == "documento_cargado":
            documents.save_pending(DocumentRecord("doc-1", "titulo.pdf"))
        elif event_type == "documento_revisado":
            documents.review("doc-1", vehicle)
        else:
            documents.confirm("doc-1", vehicle)
    assert documents.list_all() == before_documents
    assert documents.history_repository.list_all() == before_events
    assert vehicles.list_all() == []


def test_same_timestamp_uses_insertion_order_as_tiebreaker(repositories):
    path, _, documents = repositories
    documents.save_pending(DocumentRecord("first", "uno.pdf"))
    documents.save_pending(DocumentRecord("second", "dos.pdf"))
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("UPDATE history_events SET fecha_evento = ?", ("2026-10-24T12:00:00.000000+00:00",))
    assert [event.id_documento for event in documents.history_repository.list_all()] == ["second", "first"]


def test_concurrent_confirmations_record_exactly_one_registration_event(repositories):
    _, vehicles, documents = repositories
    documents.save_pending(DocumentRecord("doc-1", "titulo.pdf"))
    vehicle = VehicleRecord("AB123CD", "Toyota", "Corolla", "M1", "C1", 2020)
    documents.review("doc-1", vehicle)
    barrier = Barrier(2)

    def confirm():
        barrier.wait(timeout=10)
        try:
            documents.confirm("doc-1", vehicle)
            return "registered"
        except DocumentConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: confirm(), range(2))) == ["conflict", "registered"]
    assert len(vehicles.list_all()) == 1
    assert [event.tipo_evento for event in documents.history_repository.list_all()] == [
        "documento_registrado", "documento_revisado", "documento_cargado",
    ]
