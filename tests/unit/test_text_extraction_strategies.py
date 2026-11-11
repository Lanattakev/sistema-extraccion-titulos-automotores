"""tests/unit/test_text_extraction_strategies.py - Estrategias, fabrica y compatibilidad."""

import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfWriter

from src.application.document_errors import InvalidDocument, UnsupportedDocument
from src.application.dtos.document_dtos import Document
from src.application.text_extraction import PdfTextExtractor, TextExtractor, pdf_text_result
from src.infrastructure.document_processing import read_document_text
from src.infrastructure.extracted_text import ExtractedText
from src.infrastructure.extraction.factory import TextExtractorFactory
from src.infrastructure.extraction.image_ocr import ImageOcrExtractor
from src.infrastructure.extraction.native_pdf import NativePdfExtractor
from src.infrastructure.extraction.scanned_pdf import ScannedPdfOcrExtractor
from src.infrastructure.image_text_extraction import extract_image_text, get_settings, pytesseract
from src.infrastructure.pdf_text_extraction import extract_pdf_text, extract_scanned_pdf_text
from src.infrastructure.persistence.local_document_storage import Document as StoredDocument
from tests.test_documents import make_pdf


class FakeTextExtractor(TextExtractor):
    def __init__(self, text="", error=None):
        self.text = text
        self.error = error
        self.calls = []

    def extract(self, document: Document, path: Path) -> ExtractedText:
        self.calls.append((document, path))
        if self.error is not None:
            raise self.error
        return pdf_text_result(document, self.text)


@pytest.fixture
def document():
    return Document("synthetic-id", "titulo.pdf", "synthetic.pdf", "application/pdf", 1)


@pytest.mark.parametrize(
    "text",
    [
        "Dominio: AB123CD",
        "Marca: Toyota",
        "Modelo: Corolla",
        "Motor: M123",
        "Chasis: C456",
        "Modelo Anio: 2020",
    ],
)
def test_one_valid_native_field_is_enough_to_avoid_ocr(document, tmp_path, text):
    native, scanned = FakeTextExtractor(text), FakeTextExtractor("OCR")
    result = PdfTextExtractor(native, scanned).extract(document, tmp_path / "original.pdf")
    assert result.texto_extraido == text
    assert result.requiere_ocr is False
    assert result.mensaje == "Texto extraido correctamente."
    assert len(native.calls) == 1
    assert scanned.calls == []


@pytest.mark.parametrize("text", ["", "Texto auxiliar", "Dominio: ilegible", "Motor: SIN DATOS"])
def test_unusable_native_text_triggers_injected_ocr(document, tmp_path, text):
    native, scanned = FakeTextExtractor(text), FakeTextExtractor("Dominio: CD456EF")
    path = tmp_path / "original.pdf"
    result = PdfTextExtractor(native, scanned).extract(document, path)
    assert result.texto_extraido == "Dominio: CD456EF"
    assert result.cantidad_caracteres == len(result.texto_extraido)
    assert scanned.calls == [(document, path)]


def test_invalid_native_pdf_is_not_silently_retried_as_scanned(document, tmp_path):
    error = InvalidDocument("PDF invalido")
    scanned = FakeTextExtractor("OCR")
    with pytest.raises(InvalidDocument) as raised:
        PdfTextExtractor(FakeTextExtractor(error=error), scanned).extract(
            document, tmp_path / "bad.pdf"
        )
    assert raised.value is error
    assert not scanned.calls


def test_empty_ocr_preserves_review_message(document, tmp_path):
    result = PdfTextExtractor(FakeTextExtractor("auxiliar"), FakeTextExtractor()).extract(
        document, tmp_path / "scan.pdf"
    )
    assert result.texto_extraido == ""
    assert result.cantidad_caracteres == 0
    assert result.requiere_ocr is True
    assert result.mensaje == "OCR no obtuvo texto util; se requiere revision humana."


def test_factory_selects_independent_engines_and_common_contract():
    factory = TextExtractorFactory()
    pdf = factory.create("application/pdf")
    assert isinstance(pdf, PdfTextExtractor)
    assert isinstance(pdf.native, NativePdfExtractor)
    assert isinstance(pdf.scanned, ScannedPdfOcrExtractor)
    assert isinstance(factory.create("image/jpeg"), ImageOcrExtractor)
    assert isinstance(factory.create("image/png"), ImageOcrExtractor)
    for extractor in [pdf, pdf.native, pdf.scanned, factory.create("image/png")]:
        assert isinstance(extractor, TextExtractor)


@pytest.mark.parametrize("mime", ["image/gif", "application/octet-stream", "", "APPLICATION/PDF"])
def test_unknown_mime_keeps_controlled_error(mime):
    with pytest.raises(UnsupportedDocument, match="Solo se admiten PDF, JPG/JPEG y PNG."):
        TextExtractorFactory().create(mime)


def test_factory_can_extend_and_replace_engines_without_changing_dispatch(document):
    fake = FakeTextExtractor("Dominio: AB123CD")
    factory = TextExtractorFactory()
    factory.register("application/pdf", fake)
    result = read_document_text(document, factory)
    assert result.texto_extraido == "Dominio: AB123CD"
    assert fake.calls[0][0] is document
    assert fake.calls[0][1].name == document.nombre_interno
    document.tipo_archivo = "application/x-synthetic"
    factory.register(document.tipo_archivo, fake)
    assert read_document_text(document, factory).id_documento == document.id_documento


def test_explicit_empty_factory_has_no_implicit_defaults():
    with pytest.raises(UnsupportedDocument):
        TextExtractorFactory({}).create("application/pdf")


def test_native_strategy_reads_original_without_modifying_it(document, tmp_path):
    path = tmp_path / "titulo.pdf"
    original = make_pdf("Dominio: AB123CD")
    path.write_bytes(original)
    result = NativePdfExtractor().extract(document, path)
    assert result.texto_extraido == "Dominio: AB123CD"
    assert result.nombre_original == document.nombre_original
    assert path.read_bytes() == original


@pytest.mark.parametrize("kind", ["missing", "broken", "encrypted"])
def test_native_strategy_rejects_invalid_documents(document, tmp_path, kind):
    path = tmp_path / "bad.pdf"
    if kind == "broken":
        path.write_bytes(b"not a PDF")
    elif kind == "encrypted":
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.encrypt("synthetic")
        with path.open("wb") as stream:
            writer.write(stream)
    with pytest.raises(InvalidDocument, match="No se pudo extraer texto del PDF"):
        NativePdfExtractor().extract(document, path)


def test_scanned_strategy_preserves_page_order_and_closes_images(document, tmp_path):
    path = tmp_path / "scan.pdf"
    writer = PdfWriter()
    for _ in range(2):
        writer.add_blank_page(width=100, height=100)
    with path.open("wb") as stream:
        writer.write(stream)
    original = path.read_bytes()
    images = []
    texts = iter(["Dominio: AB123CD", "Marca: Toyota"])

    def recognize(image):
        images.append(image)
        return next(texts)

    result = ScannedPdfOcrExtractor(recognize).extract(document, path)
    assert result.texto_extraido == "Dominio: AB123CD\nMarca: Toyota"
    assert result.requiere_ocr is False
    assert result.mensaje == "Texto extraido correctamente."
    assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [path]
    assert len(images) == 2
    for image in images:
        with pytest.raises(ValueError):
            image.getpixel((0, 0))


def test_scanned_strategy_closes_image_when_ocr_fails(document, tmp_path):
    path = tmp_path / "scan.pdf"
    path.write_bytes(make_pdf())
    images = []

    def fail(image):
        images.append(image)
        raise RuntimeError("timeout")

    with pytest.raises(InvalidDocument, match="No se pudo renderizar o realizar OCR del PDF"):
        ScannedPdfOcrExtractor(fail).extract(document, path)
    assert len(images) == 1
    with pytest.raises(ValueError):
        images[0].getpixel((0, 0))


@pytest.mark.parametrize("text", ["Dominio: AB123CD", ""])
def test_image_strategy_accepts_fake_ocr_and_preserves_original(document, tmp_path, text):
    path = tmp_path / "foto.png"
    with Image.new("RGB", (20, 20), "white") as image:
        image.save(path, format="PNG")
    original = path.read_bytes()
    result = ImageOcrExtractor(lambda image: text).extract(document, path)
    assert result.texto_extraido == text
    assert result.requiere_ocr is (not bool(text))
    assert result.cantidad_caracteres == len(text)
    assert path.read_bytes() == original


def test_image_strategy_wraps_ocr_errors(document, tmp_path):
    path = tmp_path / "foto.png"
    with Image.new("RGB", (20, 20), "white") as image:
        image.save(path, format="PNG")

    def fail(image):
        raise RuntimeError("timeout")

    with pytest.raises(InvalidDocument, match="No se pudo realizar OCR"):
        ImageOcrExtractor(fail).extract(document, path)


def test_legacy_functions_and_types_remain_compatible(document, tmp_path, monkeypatch):
    assert StoredDocument is Document
    assert get_settings() is not None
    monkeypatch.setattr(pytesseract, "image_to_string", lambda *args, **kwargs: "Dominio: AB123CD")
    pdf = tmp_path / "texto.pdf"
    pdf.write_bytes(make_pdf("Dominio: CD456EF"))
    assert extract_pdf_text(document, pdf).texto_extraido == "Dominio: CD456EF"
    scan = tmp_path / "scan.pdf"
    scan.write_bytes(make_pdf())
    assert extract_scanned_pdf_text(scan) == "Dominio: AB123CD"
    image_path = tmp_path / "foto.png"
    with Image.new("RGB", (20, 20), "white") as image:
        image.save(image_path, format="PNG")
    result = extract_image_text(document, image_path)
    assert isinstance(result, ExtractedText)
    assert result.texto_extraido == "Dominio: AB123CD"


def test_protocol_and_pdf_policy_import_without_infrastructure_or_ocr():
    code = """
import sys
from src.application.text_extraction import TextExtractor, PdfTextExtractor
for name in sys.modules:
    assert not name.startswith(('fastapi', 'starlette', 'src.infrastructure', 'pypdf', 'pytesseract'))
"""
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", code], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
