"""tests/unit/test_repository_contracts.py - Routers con repositorios en memoria."""

from dataclasses import asdict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.domain.document_record import DocumentRecord
from src.domain.history_event import HistoryEvent
from src.domain.repositories import (
    DocumentConflictError,
    DocumentNotFoundError,
    DocumentRepository,
    HistoryRepository,
    VehicleRepository,
)
from src.domain.vehicle_record import VehicleIntake, VehicleRecord
from src.infrastructure.fastapi.routers import documents, history, vehicles


class MemoryVehicleRepository(VehicleRepository):
    def __init__(self):
        self.records = {}

    def save(self, intake: VehicleIntake) -> None:
        self.records[intake.id_interno] = intake

    def get_by_id(self, id_interno: str) -> VehicleIntake | None:
        return self.records.get(id_interno)

    def list_all(self) -> list[VehicleIntake]:
        return list(self.records.values())


class MemoryHistoryRepository(HistoryRepository):
    def __init__(self):
        self.events = []

    def list_all(self) -> list[HistoryEvent]:
        return list(reversed(self.events))


class MemoryDocumentRepository(DocumentRepository):
    def __init__(self, vehicle_repository, history_repository):
        self.records = {}
        self.vehicles = vehicle_repository
        self.history = history_repository

    def save_pending(self, document: DocumentRecord) -> None:
        previous = self.records.get(document.id_documento)
        if previous is None or previous.estado == "pendiente":
            self.records[document.id_documento] = document

    def list_all(self) -> list[DocumentRecord]:
        return list(self.records.values())

    def review(self, document_id: str, vehicle: VehicleRecord) -> DocumentRecord:
        document = self.records.get(document_id)
        if document is None:
            raise DocumentNotFoundError("Documento no encontrado.")
        if document.estado == "registrado":
            raise DocumentConflictError("El documento ya esta registrado.")
        for key, value in asdict(vehicle).items():
            setattr(document, key, value)
        document.estado = "revisado"
        return document

    def confirm(self, document_id: str, vehicle: VehicleRecord) -> VehicleIntake:
        document = self.review(document_id, vehicle)
        intake = VehicleIntake(vehicle, document.nombre_original, requiere_revision=False)
        self.vehicles.save(intake)
        document.estado = "registrado"
        document.id_interno = intake.id_interno
        self.history.events.append(
            HistoryEvent(document_id, "documento_registrado", document.nombre_original)
        )
        return intake


@pytest.fixture
def memory_client():
    vehicle_repository = MemoryVehicleRepository()
    history_repository = MemoryHistoryRepository()
    document_repository = MemoryDocumentRepository(vehicle_repository, history_repository)
    document_repository.save_pending(DocumentRecord("document-1", "titulo.pdf"))
    app = FastAPI()
    app.include_router(documents.router, prefix="/api/v1")
    app.include_router(vehicles.router, prefix="/api/v1")
    app.include_router(history.router, prefix="/api/v1")
    app.state.vehicle_repository = vehicle_repository
    app.state.document_repository = document_repository
    app.state.history_repository = history_repository
    with TestClient(app) as client:
        yield client


FIELDS = {
    "patente": " ab123cd ",
    "marca": "Toyota",
    "modelo": "Corolla",
    "numero_motor": "m123",
    "numero_chasis": "c456",
    "anio": 2020,
}


def test_vehicle_routes_use_replaceable_repository(memory_client):
    response = memory_client.post(
        "/api/v1/vehicles", json={**FIELDS, "archivo_origen": "titulo.pdf"}
    )
    assert response.status_code == 201
    intake = response.json()
    assert intake["vehicle"]["patente"] == "AB123CD"
    assert intake["requiere_revision"] is True
    assert memory_client.get("/api/v1/vehicles").json() == [intake]
    assert memory_client.get(f"/api/v1/vehicles/{intake['id_interno']}").json() == intake
    assert memory_client.get("/api/v1/vehicles/missing").status_code == 404


def test_document_routes_and_history_use_replaceable_repositories(memory_client):
    assert memory_client.get("/api/v1/history").json() == []
    pending = memory_client.get("/api/v1/documents").json()
    assert pending[0]["estado"] == "pendiente"
    reviewed = memory_client.patch("/api/v1/documents/document-1/review", json=FIELDS)
    assert reviewed.status_code == 200
    assert reviewed.json()["estado"] == "revisado"
    response = memory_client.post("/api/v1/documents/document-1/confirm", json=FIELDS)
    assert response.status_code == 201
    assert response.json()["requiere_revision"] is False
    events = memory_client.get("/api/v1/history").json()
    assert events[0]["tipo_evento"] == "documento_registrado"
    assert events[0]["id_documento"] == "document-1"
    assert memory_client.get("/api/v1/documents").json()[0]["estado"] == "registrado"


@pytest.mark.parametrize("operation", ["review", "confirm"])
def test_domain_errors_keep_http_status_codes(memory_client, operation):
    request = memory_client.patch if operation == "review" else memory_client.post
    missing = request(f"/api/v1/documents/missing/{operation}", json=FIELDS)
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Documento no encontrado."}
    assert (
        memory_client.post("/api/v1/documents/document-1/confirm", json=FIELDS).status_code == 201
    )
    conflict = request(f"/api/v1/documents/document-1/{operation}", json=FIELDS)
    assert conflict.status_code == 409
    assert conflict.json() == {"detail": "El documento ya esta registrado."}


def test_memory_repositories_satisfy_runtime_contracts(memory_client):
    state = memory_client.app.state
    assert isinstance(state.document_repository, DocumentRepository)
    assert isinstance(state.vehicle_repository, VehicleRepository)
    assert isinstance(state.history_repository, HistoryRepository)
