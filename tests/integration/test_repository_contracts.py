"""tests/integration/test_repository_contracts.py - Compatibilidad SQLite y contratos."""

from src.domain.document_record import DocumentRecord
from src.domain.repositories import (
    DocumentConflictError,
    DocumentNotFoundError,
    DocumentRepository,
    HistoryRepository,
    VehicleRepository,
)
from src.domain.vehicle_record import VehicleRecord
from src.infrastructure.persistence import sqlite_document_repository
from src.infrastructure.persistence.sqlite_document_repository import SQLiteDocumentRepository
from src.infrastructure.persistence.sqlite_vehicle_repository import SQLiteVehicleRepository


def test_sqlite_repositories_implement_domain_contracts(tmp_path):
    path = tmp_path / "contracts.db"
    vehicles: VehicleRepository = SQLiteVehicleRepository(path)
    sqlite_documents = SQLiteDocumentRepository(path)
    documents: DocumentRepository = sqlite_documents
    history: HistoryRepository = sqlite_documents.history_repository
    assert isinstance(vehicles, VehicleRepository)
    assert isinstance(documents, DocumentRepository)
    assert isinstance(history, HistoryRepository)
    documents.save_pending(DocumentRecord("document-1", "titulo.pdf"))
    vehicle = VehicleRecord("AB123CD", "Toyota", "Corolla", "M123", "C456", 2020)
    documents.review("document-1", vehicle)
    intake = documents.confirm("document-1", vehicle)
    assert vehicles.get_by_id(intake.id_interno) == intake
    assert vehicles.list_all() == [intake]
    assert intake.requiere_revision is False
    assert documents.list_all()[0].estado == "registrado"
    assert [event.tipo_evento for event in history.list_all()] == [
        "documento_registrado",
        "documento_revisado",
        "documento_cargado",
    ]


def test_legacy_error_imports_preserve_identity():
    assert sqlite_document_repository.DocumentNotFoundError is DocumentNotFoundError
    assert sqlite_document_repository.DocumentConflictError is DocumentConflictError
