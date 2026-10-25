"""tests/e2e/test_document_workflow.py"""

from io import BytesIO

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
    monkeypatch.setattr(get_settings(), "DATABASE_URL", f"sqlite:///{tmp_path / 'workflow.db'}")
    with TestClient(create_app()) as connection:
        yield connection


def upload(client, text="Dominio: AB123CD"):
    response = client.post("/api/v1/documents/batch", files=[
        ("files", ("titulo.pdf", make_pdf(text))),
    ])
    assert response.status_code == 200
    assert response.json()[0]["fallo"] is False
    return response.json()[0]["id_documento"]


def test_incomplete_extraction_is_persisted_pending_without_invented_fields(client):
    document_id = upload(client)
    documents = client.get("/api/v1/documents").json()
    assert len(documents) == 1
    document = documents[0]
    assert document["id_documento"] == document_id
    assert document["nombre_original"] == "titulo.pdf"
    assert document["estado"] == "pendiente"
    assert document["patente"] == "AB123CD"
    for key in ("marca", "modelo", "numero_motor", "numero_chasis", "anio", "id_interno"):
        assert document[key] is None
    assert client.get("/api/v1/vehicles").json() == []


def test_pending_survives_new_application_instance(client):
    document_id = upload(client)
    with TestClient(create_app()) as reopened:
        saved = reopened.get("/api/v1/documents").json()[0]
        assert saved["id_documento"] == document_id
        assert saved["estado"] == "pendiente"
        assert saved["marca"] is None


def test_legacy_files_are_not_silently_imported_as_reviewed(client):
    storage.save_document(BytesIO(make_pdf()), "antiguo.pdf")
    assert client.get("/api/v1/documents").json() == []


def test_review_and_registration_survive_new_application_instances(client):
    document_id = upload(client)
    path = f"/api/v1/documents/{document_id}"
    response = client.patch(path + "/review", json=FIELDS)
    assert response.status_code == 200
    assert response.json()["estado"] == "revisado"
    assert client.get("/api/v1/vehicles").json() == []
    with TestClient(create_app()) as reopened:
        saved = reopened.get("/api/v1/documents").json()[0]
        assert saved["estado"] == "revisado"
        assert all(saved[key] == value for key, value in FIELDS.items())
        response = reopened.post(path + "/confirm", json=FIELDS)
        assert response.status_code == 201
        intake = response.json()
    with TestClient(create_app()) as reopened:
        saved = reopened.get("/api/v1/documents").json()[0]
        assert saved["estado"] == "registrado"
        assert saved["id_interno"] == intake["id_interno"]
        assert reopened.get("/api/v1/vehicles").json() == [intake]
        assert reopened.post(path + "/confirm", json=FIELDS).status_code == 409
        assert reopened.patch(path + "/review", json=FIELDS).status_code == 409
        assert reopened.get("/api/v1/vehicles").json() == [intake]


def test_extraction_never_overwrites_human_review_or_registered_state(client):
    document_id = upload(client)
    path = f"/api/v1/documents/{document_id}"
    corrections = {**FIELDS, "patente": "CD456EF"}
    assert client.patch(path + "/review", json=corrections).status_code == 200
    for state in ("revisado", "registrado"):
        assert client.post(path + "/extract-fields").status_code == 200
        saved = client.get("/api/v1/documents").json()[0]
        assert saved["estado"] == state
        assert saved["patente"] == "CD456EF"
        if state == "revisado":
            assert client.post(path + "/confirm", json=corrections).status_code == 201


@pytest.mark.parametrize("key,value", [
    ("patente", " "), ("marca", None), ("modelo", ""), ("numero_motor", 23),
    ("numero_chasis", ""), ("anio", 0), ("anio", True), ("anio", "2020"),
    ("estado", "registrado"),
])
def test_invalid_review_leaves_document_pending(client, key, value):
    document_id = upload(client)
    response = client.patch(f"/api/v1/documents/{document_id}/review", json={**FIELDS, key: value})
    assert response.status_code == 422
    assert client.get("/api/v1/documents").json()[0]["estado"] == "pendiente"
    assert client.get("/api/v1/vehicles").json() == []


def test_review_requires_six_fields_and_existing_document(client):
    document_id = upload(client)
    assert client.patch(f"/api/v1/documents/{document_id}/review", json={}).status_code == 422
    assert client.patch("/api/v1/documents/missing/review", json=FIELDS).status_code == 404


def test_stale_confirmation_cannot_overwrite_a_new_review(client):
    document_id = upload(client)
    path = f"/api/v1/documents/{document_id}"
    client.patch(path + "/review", json=FIELDS)
    changed = {**FIELDS, "marca": "Honda"}
    client.patch(path + "/review", json=changed)
    assert client.post(path + "/confirm", json=FIELDS).status_code == 409
    assert client.get("/api/v1/vehicles").json() == []
    assert client.get("/api/v1/documents").json()[0]["marca"] == "Honda"


def test_mixed_batch_only_persists_successful_documents(client):
    response = client.post("/api/v1/documents/batch", files=[
        ("files", ("uno.pdf", make_pdf("Dominio: AB123CD"))),
        ("files", ("roto.pdf", b"invalid pdf")),
        ("files", ("tres.pdf", make_pdf("Dominio: CD456EF"))),
    ])
    assert [item["fallo"] for item in response.json()] == [False, True, False]
    saved = client.get("/api/v1/documents").json()
    assert [item["nombre_original"] for item in saved] == ["uno.pdf", "tres.pdf"]
    assert all(item["estado"] == "pendiente" for item in saved)


def test_legacy_explicit_confirmation_still_works_but_cannot_repeat(client):
    response = client.post("/api/v1/documents", files={"file": ("titulo.pdf", make_pdf())})
    path = f"/api/v1/documents/{response.json()['id_documento']}/confirm"
    assert client.post(path, json=FIELDS).status_code == 201
    assert client.post(path, json=FIELDS).status_code == 409
    assert client.get("/api/v1/documents").json()[0]["estado"] == "registrado"
    assert len(client.get("/api/v1/vehicles").json()) == 1
