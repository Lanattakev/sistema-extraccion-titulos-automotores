"""tests/test_documents.py"""

import json
from io import BytesIO
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, StreamObject

from src.infrastructure.persistence import local_document_storage as storage
from src.main import create_app


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "UPLOAD_DIRECTORY", tmp_path / "uploads")
    # Este endpoint no necesita inicializar el repositorio de vehiculos.
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.mark.parametrize("name,mime,content", [
    ("titulo.pdf", "application/pdf", b"%PDF-1.4\nexample"),
    ("foto.jpg", "image/jpeg", b"\xff\xd8\xffexample"),
    ("foto.JPEG", "image/jpeg", b"\xff\xd8\xffexample"),
    ("foto.png", "image/png", b"\x89PNG\r\n\x1a\nexample"),
])
def test_valid_upload(client, name, mime, content):
    response = client.post("/api/v1/documents", files={"file": (name, content, mime)})
    assert response.status_code == 201
    data = response.json()
    assert str(UUID(data["id_documento"])) == data["id_documento"]
    assert data["nombre_original"] == name
    assert data["nombre_interno"] == data["id_documento"] + "." + name.rsplit(".", 1)[1].lower()
    assert data["tipo_archivo"] == mime
    assert data["tamanio_bytes"] == len(content)
    assert (storage.UPLOAD_DIRECTORY / data["nombre_interno"]).read_bytes() == content
    metadata = storage.UPLOAD_DIRECTORY / (data["id_documento"] + ".json")
    assert json.loads(metadata.read_text(encoding="utf-8")) == data


@pytest.mark.parametrize("name", ["script.exe", "../../archivo.pdf", "..\\..\\archivo.pdf",
                                      "C:\\archivo.pdf", "/archivo.pdf", ""])
def test_reject_invalid_names(client, name):
    response = client.post("/api/v1/documents", files={"file": (name, b"example")})
    assert response.status_code in (400, 422)
    assert not storage.UPLOAD_DIRECTORY.exists()


def test_reject_large_upload(client):
    response = client.post("/api/v1/documents", files={
        "file": ("titulo.pdf", b"x" * (storage.MAX_DOCUMENT_BYTES + 1))})
    assert response.status_code == 413
    assert list(storage.UPLOAD_DIRECTORY.iterdir()) == []


def test_unique_names(client):
    results = [client.post("/api/v1/documents", files={
        "file": ("titulo.pdf", b"example")}).json() for _ in range(2)]
    assert results[0]["nombre_interno"] != results[1]["nombre_interno"]
    assert results[0]["id_documento"] != results[1]["id_documento"]


def test_reject_multiple_files(client):
    response = client.post("/api/v1/documents", files=[
        ("file", ("uno.pdf", b"one")), ("file", ("dos.pdf", b"two"))])
    assert response.status_code == 400
    assert not storage.UPLOAD_DIRECTORY.exists()


def test_reject_empty_file(client):
    response = client.post("/api/v1/documents", files={"file": ("vacio.pdf", b"")})
    assert response.status_code == 400
    assert list(storage.UPLOAD_DIRECTORY.iterdir()) == []


def make_pdf(text=None):
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    if text is not None:
        font = DictionaryObject({
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        })
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font}),
        })
        stream = StreamObject()
        stream.set_data(f"BT /F1 12 Tf 20 200 Td ({text}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def upload_for_extraction(client, content, name="documento.pdf"):
    response = client.post("/api/v1/documents", files={"file": (name, content)})
    assert response.status_code == 201
    return response.json()


def test_extract_pdf_text(client):
    document = upload_for_extraction(client, make_pdf("Texto del documento"))
    response = client.post(f"/api/v1/documents/{document['id_documento']}/extract-text")
    assert response.status_code == 200
    data = response.json()
    assert data["id_documento"] == document["id_documento"]
    assert data["nombre_original"] == "documento.pdf"
    assert data["texto_extraido"] == "Texto del documento"
    assert data["cantidad_caracteres"] == len(data["texto_extraido"])
    assert data["requiere_ocr"] is False


@pytest.mark.parametrize("document_id", ["00000000-0000-0000-0000-000000000000", "inexistente"])
def test_extract_missing_document(client, document_id):
    response = client.post(f"/api/v1/documents/{document_id}/extract-text")
    assert response.status_code == 404


def test_extract_non_pdf(client):
    document = upload_for_extraction(client, b"image", "foto.png")
    response = client.post(f"/api/v1/documents/{document['id_documento']}/extract-text")
    assert response.status_code == 415


def test_extract_pdf_without_text(client):
    document = upload_for_extraction(client, make_pdf())
    response = client.post(f"/api/v1/documents/{document['id_documento']}/extract-text")
    assert response.status_code == 200
    data = response.json()
    assert data["texto_extraido"] == ""
    assert data["cantidad_caracteres"] == 0
    assert data["requiere_ocr"] is True
    assert "probablemente requiera OCR" in data["mensaje"]


def test_extract_preserves_original(client):
    content = make_pdf("Original intacto")
    document = upload_for_extraction(client, content)
    path = storage.UPLOAD_DIRECTORY / document["nombre_interno"]
    before = {p.name: p.read_bytes() for p in storage.UPLOAD_DIRECTORY.iterdir()}
    original_mtime = path.stat().st_mtime_ns
    response = client.post(f"/api/v1/documents/{document['id_documento']}/extract-text")
    assert response.status_code == 200
    assert path.read_bytes() == content
    assert path.stat().st_mtime_ns == original_mtime
    assert {p.name: p.read_bytes() for p in storage.UPLOAD_DIRECTORY.iterdir()} == before


def test_extract_invalid_pdf(client):
    document = upload_for_extraction(client, b"This is not a PDF")
    response = client.post(f"/api/v1/documents/{document['id_documento']}/extract-text")
    assert response.status_code == 400


def test_extract_missing_original(client):
    document = upload_for_extraction(client, make_pdf("Texto"))
    (storage.UPLOAD_DIRECTORY / document["nombre_interno"]).unlink()
    response = client.post(f"/api/v1/documents/{document['id_documento']}/extract-text")
    assert response.status_code == 404


def test_extract_fields_does_not_save_vehicle(client, monkeypatch):
    from src.infrastructure.persistence.sqlite_vehicle_repository import SQLiteVehicleRepository

    def forbidden_save(*args, **kwargs):
        pytest.fail("El analisis no debe guardar vehiculos")

    monkeypatch.setattr(SQLiteVehicleRepository, "save", forbidden_save)
    repository = client.app.state.vehicle_repository
    before_vehicles = repository.list_all()
    document = upload_for_extraction(client, make_pdf(
        "Dominio: AB123CD Marca: Ejemplo Modelo: Ruta Motor: M123 Chasis: C456 Anio: 2020"
    ))
    before_files = {p.name: p.read_bytes() for p in storage.UPLOAD_DIRECTORY.iterdir()}
    response = client.post(f"/api/v1/documents/{document['id_documento']}/extract-fields")
    assert response.status_code == 200
    assert response.json() == {
        "id_documento": document["id_documento"], "patente": "AB123CD", "marca": "Ejemplo",
        "modelo": "Ruta", "numero_motor": "M123", "numero_chasis": "C456",
        "anio": 2020, "requiere_revision": True,
    }
    assert repository.list_all() == before_vehicles
    assert {p.name: p.read_bytes() for p in storage.UPLOAD_DIRECTORY.iterdir()} == before_files


@pytest.mark.parametrize("content,name,expected", [
    (make_pdf(), "vacio.pdf", 200),
    (b"invalid", "roto.pdf", 400),
    (b"image", "foto.png", 415),
])
def test_extract_fields_handles_unreadable_text(client, content, name, expected):
    document = upload_for_extraction(client, content, name)
    response = client.post(f"/api/v1/documents/{document['id_documento']}/extract-fields")
    assert response.status_code == expected
    if expected == 200:
        assert response.json()["requiere_revision"] is True
        assert all(response.json()[field] is None for field in (
            "patente", "marca", "modelo", "numero_motor", "numero_chasis", "anio",
        ))


def test_extract_fields_missing_document(client):
    response = client.post("/api/v1/documents/inexistente/extract-fields")
    assert response.status_code == 404
