"""tests/integration/test_sqlite_document_repository.py"""

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
    path = tmp_path / "workflow.db"
    vehicles = SQLiteVehicleRepository(path)
    documents = SQLiteDocumentRepository(path)
    documents.save_pending(DocumentRecord("document-1", "titulo.pdf"))
    vehicle = VehicleRecord("AB123CD", "Toyota", "Corolla", "M123", "C456", 2020)
    documents.review("document-1", vehicle)
    return path, vehicles, documents, vehicle


def test_concurrent_confirmations_create_exactly_one_vehicle(repositories):
    path, vehicles, _, vehicle = repositories
    barrier = Barrier(2)

    def confirm():
        repository = SQLiteDocumentRepository(path)
        barrier.wait(timeout=10)
        try:
            repository.confirm("document-1", vehicle)
            return "registered"
        except DocumentConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: confirm(), range(2)))
    assert sorted(outcomes) == ["conflict", "registered"]
    assert len(vehicles.list_all()) == 1
    assert SQLiteDocumentRepository(path).list_all()[0].estado == "registrado"


def test_failure_updating_document_rolls_back_vehicle_insert(repositories):
    path, vehicles, documents, vehicle = repositories
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("""
            CREATE TRIGGER fail_registration BEFORE UPDATE ON documents
            WHEN NEW.estado = 'registrado'
            BEGIN SELECT RAISE(ABORT, 'simulated storage failure'); END
        """)
    with pytest.raises(sqlite3.IntegrityError, match="simulated storage failure"):
        documents.confirm("document-1", vehicle)
    assert vehicles.list_all() == []
    assert documents.list_all()[0].estado == "revisado"
    assert documents.list_all()[0].id_interno is None


def test_schema_rejects_invalid_state(repositories):
    path, _, documents, _ = repositories
    with closing(sqlite3.connect(path)) as connection, connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE documents SET estado = 'otro'")
    assert documents.list_all()[0].estado == "revisado"
