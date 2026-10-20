"""tests/test_documents.py"""

import json
from io import BytesIO
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject, StreamObject

from src.infrastructure import image_text_extraction as ocr
from src.infrastructure.persistence import local_document_storage as storage
from src.infrastructure.settings.config import get_settings
from src.main import create_app


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "UPLOAD_DIRECTORY", tmp_path / "uploads")
    monkeypatch.setattr(get_settings(), "DATABASE_URL", f"sqlite:///{tmp_path / 'vehicles.db'}")
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
    document = upload_for_extraction(client, make_pdf("Marca: Ejemplo"))
    response = client.post(f"/api/v1/documents/{document['id_documento']}/extract-text")
    assert response.status_code == 200
    data = response.json()
    assert data["id_documento"] == document["id_documento"]
    assert data["nombre_original"] == "documento.pdf"
    assert data["texto_extraido"] == "Marca: Ejemplo"
    assert data["cantidad_caracteres"] == len(data["texto_extraido"])
    assert data["requiere_ocr"] is False


@pytest.mark.parametrize("document_id", ["00000000-0000-0000-0000-000000000000", "inexistente"])
def test_extract_missing_document(client, document_id):
    response = client.post(f"/api/v1/documents/{document_id}/extract-text")
    assert response.status_code == 404


def test_extract_invalid_image(client):
    document = upload_for_extraction(client, b"image", "foto.png")
    response = client.post(f"/api/v1/documents/{document['id_documento']}/extract-text")
    assert response.status_code == 400


def test_extract_pdf_without_text(client, monkeypatch):
    monkeypatch.setattr(ocr.pytesseract, "image_to_string", lambda *a, **kw: "")
    document = upload_for_extraction(client, make_pdf())
    response = client.post(f"/api/v1/documents/{document['id_documento']}/extract-text")
    assert response.status_code == 200
    data = response.json()
    assert data["texto_extraido"] == ""
    assert data["cantidad_caracteres"] == 0
    assert data["requiere_ocr"] is True
    assert "OCR no obtuvo texto util" in data["mensaje"]


def test_extract_preserves_original(client):
    content = make_pdf("Marca: Original")
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
    (b"image", "foto.png", 400),
])
def test_extract_fields_handles_unreadable_text(client, monkeypatch, content, name, expected):
    monkeypatch.setattr(ocr.pytesseract, "image_to_string", lambda *a, **kw: "")
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


OCR_TEXT = (
    "DOMINIO: AB123CD\nMARCA: TOYOTA\nMODELO: COROLLA\n"
    "MOTOR: XYZ123\nCHASIS: ABC987\nMODELO AÑO: 2020"
)


def make_image(name):
    output = BytesIO()
    with Image.new("RGB", (100, 100), "white") as image:
        image.save(output, format="PNG" if name.endswith(".png") else "JPEG")
    return output.getvalue()


@pytest.mark.parametrize("name", ["foto.jpg", "foto.jpeg", "foto.png"])
def test_extract_image_text(client, monkeypatch, name):
    calls = []

    def fake_ocr(image, **kwargs):
        calls.append((image.format, kwargs))
        return OCR_TEXT

    monkeypatch.setattr(ocr.pytesseract, "image_to_string", fake_ocr)
    document = upload_for_extraction(client, make_image(name), name)
    response = client.post(f"/api/v1/documents/{document['id_documento']}/extract-text")
    assert response.status_code == 200
    assert response.json()["texto_extraido"] == OCR_TEXT
    assert response.json()["cantidad_caracteres"] == len(OCR_TEXT)
    assert response.json()["requiere_ocr"] is False
    settings = ocr.get_settings()
    assert calls == [("PNG" if name.endswith(".png") else "JPEG", {
        "lang": settings.TESSERACT_LANG, "timeout": settings.TESSERACT_TIMEOUT,
    })]
    assert ocr.pytesseract.pytesseract.tesseract_cmd == settings.TESSERACT_CMD


@pytest.mark.parametrize("text", ["", " \n\t", "... | !!!"])
def test_image_without_useful_text(client, monkeypatch, text):
    monkeypatch.setattr(ocr.pytesseract, "image_to_string", lambda *args, **kwargs: text)
    document = upload_for_extraction(client, make_image("foto.png"), "foto.png")
    base = f"/api/v1/documents/{document['id_documento']}"
    response = client.post(base + "/extract-text")
    assert response.status_code == 200
    assert response.json()["texto_extraido"] == ""
    assert response.json()["cantidad_caracteres"] == 0
    assert "no obtuvo texto util" in response.json()["mensaje"]
    fields = client.post(base + "/extract-fields")
    assert fields.status_code == 200
    assert fields.json()["requiere_revision"] is True
    assert all(fields.json()[field] is None for field in (
        "patente", "marca", "modelo", "numero_motor", "numero_chasis", "anio",
    ))


def test_extract_image_fields_does_not_save(client, monkeypatch):
    from src.infrastructure.persistence.sqlite_vehicle_repository import SQLiteVehicleRepository

    def forbidden_save(*args, **kwargs):
        pytest.fail("OCR must not save vehicles")

    monkeypatch.setattr(SQLiteVehicleRepository, "save", forbidden_save)
    monkeypatch.setattr(ocr.pytesseract, "image_to_string", lambda *args, **kwargs: OCR_TEXT)
    document = upload_for_extraction(client, make_image("foto.png"), "foto.png")
    before_files = {p.name: p.read_bytes() for p in storage.UPLOAD_DIRECTORY.iterdir()}
    before_vehicles = client.app.state.vehicle_repository.list_all()
    response = client.post(f"/api/v1/documents/{document['id_documento']}/extract-fields")
    assert response.status_code == 200
    assert response.json() == {
        "id_documento": document["id_documento"], "patente": "AB123CD", "marca": "TOYOTA",
        "modelo": "COROLLA", "numero_motor": "XYZ123", "numero_chasis": "ABC987",
        "anio": 2020, "requiere_revision": True,
    }
    assert client.app.state.vehicle_repository.list_all() == before_vehicles
    assert {p.name: p.read_bytes() for p in storage.UPLOAD_DIRECTORY.iterdir()} == before_files


@pytest.mark.parametrize("endpoint", ["extract-text", "extract-fields"])
def test_extract_unsupported_format(client, monkeypatch, endpoint):
    document = upload_for_extraction(client, make_image("foto.png"), "foto.png")
    metadata = storage.get_document(document["id_documento"])
    metadata.tipo_archivo = "image/gif"
    monkeypatch.setattr(storage, "get_document", lambda document_id: metadata)
    response = client.post(f"/api/v1/documents/{metadata.id_documento}/{endpoint}")
    assert response.status_code == 415


@pytest.mark.parametrize("error", [
    ocr.pytesseract.TesseractNotFoundError(),
    ocr.pytesseract.TesseractError(1, "OCR failed"),
    RuntimeError("Tesseract process timeout"),
])
def test_ocr_failure_is_controlled(client, monkeypatch, error):
    def fail_ocr(*args, **kwargs):
        raise error

    monkeypatch.setattr(ocr.pytesseract, "image_to_string", fail_ocr)
    document = upload_for_extraction(client, make_image("foto.png"), "foto.png")
    response = client.post(f"/api/v1/documents/{document['id_documento']}/extract-text")
    assert response.status_code == 400
    assert "No se pudo realizar OCR" in response.json()["detail"]


@pytest.mark.parametrize("endpoint", ["extract-text", "extract-fields"])
def test_scanned_pdf_fallback(client, monkeypatch, endpoint):
    from src.infrastructure.persistence.sqlite_vehicle_repository import SQLiteVehicleRepository

    def forbidden_save(*args, **kwargs):
        pytest.fail("PDF OCR must not save vehicles")

    monkeypatch.setattr(SQLiteVehicleRepository, "save", forbidden_save)
    monkeypatch.setattr(ocr.pytesseract, "image_to_string", lambda *a, **kw: OCR_TEXT)
    document = upload_for_extraction(client, make_pdf(), "escaneado.pdf")
    before = {p.name: p.read_bytes() for p in storage.UPLOAD_DIRECTORY.iterdir()}
    response = client.post(f"/api/v1/documents/{document['id_documento']}/{endpoint}")
    assert response.status_code == 200
    data = response.json()
    if endpoint == "extract-text":
        assert data["texto_extraido"] == OCR_TEXT
        assert data["cantidad_caracteres"] == len(OCR_TEXT)
        assert data["requiere_ocr"] is False
    else:
        assert data == {
            "id_documento": document["id_documento"], "patente": "AB123CD", "marca": "TOYOTA",
            "modelo": "COROLLA", "numero_motor": "XYZ123", "numero_chasis": "ABC987",
            "anio": 2020, "requiere_revision": True,
        }
    assert {p.name: p.read_bytes() for p in storage.UPLOAD_DIRECTORY.iterdir()} == before


def test_text_pdf_never_renders_or_uses_ocr(client, monkeypatch):
    from src.infrastructure import pdf_text_extraction as pdf

    def forbidden(*args, **kwargs):
        pytest.fail("PDF with text must use only pypdf")

    monkeypatch.setattr(pdf.pdfium, "PdfDocument", forbidden)
    monkeypatch.setattr(ocr.pytesseract, "image_to_string", forbidden)
    document = upload_for_extraction(client, make_pdf("Dominio: AB123CD"))
    response = client.post(f"/api/v1/documents/{document['id_documento']}/extract-fields")
    assert response.status_code == 200
    assert response.json()["patente"] == "AB123CD"
    assert response.json()["requiere_revision"] is True


def test_scanned_pdf_joins_pages_in_order(client, monkeypatch):
    writer = PdfWriter()
    for _ in range(2):
        writer.add_blank_page(width=100, height=100)
    output = BytesIO()
    writer.write(output)
    texts = iter(["DOMINIO: AB123CD", "MARCA: TOYOTA"])
    monkeypatch.setattr(ocr.pytesseract, "image_to_string", lambda *a, **kw: next(texts))
    document = upload_for_extraction(client, output.getvalue())
    response = client.post(f"/api/v1/documents/{document['id_documento']}/extract-text")
    assert response.status_code == 200
    assert response.json()["texto_extraido"] == "DOMINIO: AB123CD\nMARCA: TOYOTA"


@pytest.mark.parametrize("failure", ["render", "ocr"])
def test_scanned_pdf_failure_is_controlled(client, monkeypatch, failure):
    from src.infrastructure import pdf_text_extraction as pdf

    def fail(*args, **kwargs):
        raise RuntimeError("Rendering or OCR failed")

    if failure == "render":
        monkeypatch.setattr(pdf.pdfium, "PdfDocument", fail)
    else:
        monkeypatch.setattr(ocr.pytesseract, "image_to_string", fail)
    document = upload_for_extraction(client, make_pdf())
    response = client.post(f"/api/v1/documents/{document['id_documento']}/extract-fields")
    assert response.status_code == 400


@pytest.mark.parametrize("endpoint", ["extract-text", "extract-fields"])
@pytest.mark.parametrize("auxiliary", [
    "19/10/2026 titulo_impreso.pdf", "Dominio: ilegible", "Documento sin datos del vehiculo",
])
def test_auxiliary_text_with_scanned_page_uses_ocr(client, monkeypatch, endpoint, auxiliary):
    # PDF con una imagen real y una capa de texto auxiliar que pypdf puede leer.
    scanned = BytesIO()
    with Image.new("RGB", (100, 100), "white") as image:
        image.save(scanned, format="PDF")
    reader = PdfReader(BytesIO(scanned.getvalue()))
    page = reader.pages[0]
    page.merge_page(PdfReader(BytesIO(make_pdf(auxiliary))).pages[0])
    writer = PdfWriter()
    writer.add_page(page)
    output = BytesIO()
    writer.write(output)
    assert auxiliary in PdfReader(BytesIO(output.getvalue())).pages[0].extract_text()
    calls = []

    def fake_ocr(image, **kwargs):
        calls.append(image.size)
        return OCR_TEXT

    monkeypatch.setattr(ocr.pytesseract, "image_to_string", fake_ocr)
    document = upload_for_extraction(client, output.getvalue())
    response = client.post(f"/api/v1/documents/{document['id_documento']}/{endpoint}")
    assert response.status_code == 200
    assert len(calls) == 1
    if endpoint == "extract-text":
        assert response.json()["texto_extraido"] == OCR_TEXT
    else:
        assert response.json() == {
            "id_documento": document["id_documento"], "patente": "AB123CD", "marca": "TOYOTA",
            "modelo": "COROLLA", "numero_motor": "XYZ123", "numero_chasis": "ABC987",
            "anio": 2020, "requiere_revision": True,
        }


@pytest.fixture
def reviewed_fields():
    return {
        "patente": " cd456ef ", "marca": "Honda", "modelo": "Civic",
        "numero_motor": "motor2", "numero_chasis": "chasis2", "anio": 2022,
    }


def test_confirm_document_saves_reviewed_fields(client, reviewed_fields):
    document = upload_for_extraction(client, make_pdf("Marca: Ejemplo"), "titulo_original.pdf")
    response = client.post(
        f"/api/v1/documents/{document['id_documento']}/confirm", json=reviewed_fields,
    )
    assert response.status_code == 201
    intake = response.json()
    assert intake["archivo_origen"] == "titulo_original.pdf"
    assert intake["vehicle"] == {
        **reviewed_fields, "patente": "CD456EF", "numero_motor": "MOTOR2",
        "numero_chasis": "CHASIS2",
    }
    assert intake["requiere_revision"] is False
    assert intake["fecha_ingreso"]
    assert str(UUID(intake["id_interno"])) == intake["id_interno"]
    assert client.get(f"/api/v1/vehicles/{intake['id_interno']}").json() == intake
    assert client.get("/api/v1/vehicles").json() == [intake]


def test_confirm_keeps_human_corrections_instead_of_ocr(client, monkeypatch, reviewed_fields):
    monkeypatch.setattr(ocr.pytesseract, "image_to_string", lambda *a, **kw: OCR_TEXT)
    document = upload_for_extraction(client, make_image("foto.png"), "foto.png")
    base = f"/api/v1/documents/{document['id_documento']}"
    proposal = client.post(base + "/extract-fields")
    assert proposal.status_code == 200
    assert proposal.json()["patente"] == "AB123CD"
    assert proposal.json()["requiere_revision"] is True
    assert client.get("/api/v1/vehicles").json() == []

    def forbidden_ocr(*args, **kwargs):
        pytest.fail("Confirmation must not rerun OCR")

    monkeypatch.setattr(ocr.pytesseract, "image_to_string", forbidden_ocr)
    response = client.post(base + "/confirm", json=reviewed_fields)
    assert response.status_code == 201
    assert response.json()["requiere_revision"] is False
    assert response.json()["vehicle"]["patente"] == "CD456EF"
    assert response.json()["vehicle"]["marca"] == "Honda"
    assert response.json()["vehicle"]["anio"] == 2022
    assert client.get("/api/v1/vehicles").json() == [response.json()]
    saved = client.app.state.vehicle_repository.get_by_id(response.json()["id_interno"])
    assert saved.requiere_revision is False


@pytest.mark.parametrize("document_id", ["missing", "00000000-0000-0000-0000-000000000000"])
def test_confirm_missing_document(client, reviewed_fields, document_id):
    response = client.post(f"/api/v1/documents/{document_id}/confirm", json=reviewed_fields)
    assert response.status_code == 404
    assert client.get("/api/v1/vehicles").json() == []


@pytest.mark.parametrize("field,value", [
    ("patente", " "), ("marca", None), ("modelo", ""), ("numero_motor", " "),
    ("numero_chasis", 42), ("anio", 0), ("anio", True), ("anio", "2020"),
    ("archivo_origen", "fake.pdf"), ("requiere_revision", False),
])
def test_confirm_invalid_fields_do_not_save(client, reviewed_fields, field, value):
    document = upload_for_extraction(client, make_pdf())
    response = client.post(
        f"/api/v1/documents/{document['id_documento']}/confirm",
        json={**reviewed_fields, field: value},
    )
    assert response.status_code == 422
    assert client.get("/api/v1/vehicles").json() == []


def test_confirm_requires_all_six_fields(client, reviewed_fields):
    document = upload_for_extraction(client, make_pdf())
    del reviewed_fields["anio"]
    response = client.post(
        f"/api/v1/documents/{document['id_documento']}/confirm", json=reviewed_fields,
    )
    assert response.status_code == 422
    assert client.get("/api/v1/vehicles").json() == []
