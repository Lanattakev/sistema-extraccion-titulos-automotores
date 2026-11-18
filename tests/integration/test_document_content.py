"""tests/integration/test_document_content.py - Originales inline sin alterar el flujo."""

import json
from io import BytesIO
from urllib.parse import quote
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from src.application.dtos.document_dtos import Document
from src.infrastructure.persistence import local_document_storage as storage
from src.infrastructure.settings.config import get_settings
from src.main import create_app
from tests.test_documents import make_pdf

FIELDS = {
    "patente": "AB123CD",
    "marca": "Toyota",
    "modelo": "Corolla",
    "numero_motor": "M123",
    "numero_chasis": "C456",
    "anio": 2020,
}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "UPLOAD_DIRECTORY", tmp_path / "uploads")
    monkeypatch.setattr(get_settings(), "DATABASE_URL", f"sqlite:///{tmp_path / 'content.db'}")
    with TestClient(create_app()) as connection:
        yield connection


def original_bytes(extension):
    if extension.lower() == "pdf":
        return make_pdf("Dominio: AB123CD")
    output = BytesIO()
    with Image.new("RGB", (20, 12), "white") as image:
        image.save(output, format="PNG" if extension.lower() == "png" else "JPEG")
    return output.getvalue()


def upload(client, name="titulo.pdf"):
    content = original_bytes(name.rsplit(".", 1)[1])
    response = client.post("/api/v1/documents", files={"file": (name, content)})
    assert response.status_code == 201
    return response.json(), content


@pytest.mark.parametrize(
    "name,mime",
    [
        ("titulo.PDF", "application/pdf"),
        ("foto.jpg", "image/jpeg"),
        ("foto.JPEG", "image/jpeg"),
        ("foto.png", "image/png"),
    ],
)
def test_content_returns_original_inline_with_correct_mime(client, name, mime):
    document, content = upload(client, name)
    response = client.get(f"/api/v1/documents/{document['id_documento']}/content")
    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"] == mime
    assert response.headers["content-disposition"].startswith("inline;")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_inline_filename_handles_unicode_and_quotes(client):
    name = 'Título "revisado".pdf'
    # El cliente multipart escapa las comillas antes de enviarlas: guardar el
    # original directamente permite comprobar la cabecera sin cambiar la carga.
    document = storage.save_document(BytesIO(make_pdf()), name)
    response = client.get(f"/api/v1/documents/{document.id_documento}/content")
    assert response.status_code == 200
    assert response.headers["content-disposition"] == f"inline; filename*=utf-8''{quote(name)}"


@pytest.mark.parametrize("document_id", [str(uuid4()), "missing", "..%5Csecret.pdf"])
def test_content_missing_or_invalid_id_returns_404(client, document_id):
    response = client.get(f"/api/v1/documents/{document_id}/content")
    assert response.status_code == 404


@pytest.mark.parametrize("missing", ["original", "metadata"])
def test_content_missing_physical_file_or_metadata_returns_404(client, missing):
    document, _ = upload(client)
    filename = (
        document["nombre_interno"] if missing == "original" else document["id_documento"] + ".json"
    )
    (storage.UPLOAD_DIRECTORY / filename).unlink()
    response = client.get(f"/api/v1/documents/{document['id_documento']}/content")
    assert response.status_code == 404
    assert response.json()["detail"] == "Documento no encontrado."


def test_content_supports_pdf_range_requests(client):
    document, content = upload(client)
    response = client.get(
        f"/api/v1/documents/{document['id_documento']}/content", headers={"Range": "bytes=0-7"}
    )
    assert response.status_code == 206
    assert response.content == content[:8]
    assert response.headers["content-range"] == f"bytes 0-7/{len(content)}"


def test_content_never_changes_originals_document_states_or_history(client):
    document, content = upload(client)
    path = f"/api/v1/documents/{document['id_documento']}"
    originals = {p.name: p.read_bytes() for p in storage.UPLOAD_DIRECTORY.iterdir()}
    for state in ("pendiente", "revisado", "registrado"):
        before = {
            route: client.get(route).json()
            for route in ("/api/v1/documents", "/api/v1/vehicles", "/api/v1/history")
        }
        assert before["/api/v1/documents"][0]["estado"] == state
        assert client.get(path + "/content").content == content
        assert {route: client.get(route).json() for route in before} == before
        assert {p.name: p.read_bytes() for p in storage.UPLOAD_DIRECTORY.iterdir()} == originals
        if state == "pendiente":
            assert client.patch(path + "/review", json=FIELDS).status_code == 200
        elif state == "revisado":
            assert client.post(path + "/confirm", json=FIELDS).status_code == 201


def test_content_rejects_path_outside_storage_even_if_loader_is_replaced(
    client, monkeypatch, tmp_path
):
    (tmp_path / "private.pdf").write_bytes(b"private")
    document = Document(str(uuid4()), "private.pdf", "../private.pdf", "application/pdf", 7)
    monkeypatch.setattr(storage, "get_document", lambda _: document)
    response = client.get(f"/api/v1/documents/{document.id_documento}/content")
    assert response.status_code == 404
    assert b"private" not in response.content


def test_content_does_not_trust_a_modified_mime_in_metadata(client):
    document, content = upload(client)
    metadata = storage.UPLOAD_DIRECTORY / (document["id_documento"] + ".json")
    metadata.write_text(json.dumps({**document, "tipo_archivo": "text/html"}), encoding="utf-8")
    response = client.get(f"/api/v1/documents/{document['id_documento']}/content")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == content
