"""tests/e2e/test_history.py"""

from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from src.infrastructure.persistence import local_document_storage as storage
from src.infrastructure.settings.config import get_settings
from src.main import create_app
from tests.test_documents import make_pdf

FIELDS = {
    "patente": "AB123CD", "marca": "Toyota", "modelo": "Corolla",
    "numero_motor": "M123", "numero_chasis": "C456", "anio": 2020,
}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "UPLOAD_DIRECTORY", tmp_path / "uploads")
    monkeypatch.setattr(get_settings(), "DATABASE_URL", f"sqlite:///{tmp_path / 'history.db'}")
    with TestClient(create_app()) as connection:
        yield connection


def upload(client):
    response = client.post("/api/v1/documents/batch", files=[
        ("files", ("titulo.pdf", make_pdf("Dominio: AB123CD"))),
    ])
    assert response.status_code == 200
    assert response.json()[0]["fallo"] is False
    return response.json()[0]["id_documento"]


def test_empty_history_remains_empty_after_gets(client):
    for _ in range(3):
        response = client.get("/api/v1/history")
        assert response.status_code == 200
        assert response.json() == []
        assert client.get("/api/v1/documents").json() == []
        assert client.get("/api/v1/vehicles").json() == []


def test_real_lifecycle_events_are_persistent_and_newest_first(client):
    started = datetime.now(timezone.utc)
    document_id = upload(client)
    path = f"/api/v1/documents/{document_id}"
    assert client.patch(path + "/review", json=FIELDS).status_code == 200
    assert client.post(path + "/confirm", json=FIELDS).status_code == 201
    history = client.get("/api/v1/history").json()
    finished = datetime.now(timezone.utc)
    assert [event["tipo_evento"] for event in history] == [
        "documento_registrado", "documento_revisado", "documento_cargado",
    ]
    assert len({event["id_evento"] for event in history}) == 3
    for event in history:
        assert str(UUID(event["id_evento"])) == event["id_evento"]
        assert event["id_documento"] == document_id
        assert event["nombre_original"] == "titulo.pdf"
        assert set(event) == {"id_evento", "id_documento", "tipo_evento", "fecha_evento", "nombre_original"}
        assert started <= datetime.fromisoformat(event["fecha_evento"]) <= finished
    dates = [datetime.fromisoformat(event["fecha_evento"]) for event in history]
    assert dates == sorted(dates, reverse=True)
    with TestClient(create_app()) as reopened:
        assert reopened.get("/api/v1/history").json() == history
    for _ in range(3):
        client.get("/api/v1/documents")
        client.get("/api/v1/vehicles")
        assert client.get("/api/v1/history").json() == history


def test_repeated_extraction_and_identical_review_do_not_duplicate_events(client):
    response = client.post("/api/v1/documents", files={
        "file": ("titulo.pdf", make_pdf("Dominio: AB123CD")),
    })
    path = f"/api/v1/documents/{response.json()['id_documento']}"
    for _ in range(2):
        assert client.post(path + "/extract-fields").status_code == 200
    assert len(client.get("/api/v1/history").json()) == 1
    for _ in range(2):
        assert client.patch(path + "/review", json=FIELDS).status_code == 200
    assert len(client.get("/api/v1/history").json()) == 2
    corrected = {**FIELDS, "modelo": "Modelo corregido"}
    assert client.patch(path + "/review", json=corrected).status_code == 200
    assert len(client.get("/api/v1/history").json()) == 3
    assert client.post(path + "/confirm", json=corrected).status_code == 201
    before = client.get("/api/v1/history").json()
    assert client.post(path + "/confirm", json=corrected).status_code == 409
    assert client.patch(path + "/review", json=corrected).status_code == 409
    assert client.get("/api/v1/history").json() == before
    assert len(client.get("/api/v1/vehicles").json()) == 1


def test_failed_operations_do_not_create_success_events(client):
    document_id = upload(client)
    path = f"/api/v1/documents/{document_id}"
    before = client.get("/api/v1/history").json()
    assert client.patch(path + "/review", json={**FIELDS, "anio": 0}).status_code == 422
    assert client.post(path + "/confirm", json={}).status_code == 422
    assert client.patch("/api/v1/documents/missing/review", json=FIELDS).status_code == 404
    assert client.get("/api/v1/history").json() == before
    assert client.patch(path + "/review", json=FIELDS).status_code == 200
    before = client.get("/api/v1/history").json()
    assert client.post(path + "/confirm", json={**FIELDS, "modelo": "Sin guardar"}).status_code == 409
    assert client.get("/api/v1/history").json() == before


def test_batch_only_records_successful_processing_including_incomplete_fields(client):
    response = client.post("/api/v1/documents/batch", files=[
        ("files", ("uno.pdf", make_pdf("Dominio: AB123CD"))),
        ("files", ("roto.pdf", b"invalid pdf")),
        ("files", ("tres.pdf", make_pdf("Dominio: CD456EF"))),
    ])
    assert [item["fallo"] for item in response.json()] == [False, True, False]
    history = client.get("/api/v1/history").json()
    assert [event["nombre_original"] for event in history] == ["tres.pdf", "uno.pdf"]
    assert all(event["tipo_evento"] == "documento_cargado" for event in history)
    assert client.get("/api/v1/vehicles").json() == []
