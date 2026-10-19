"""src/infrastructure/pdf_text_extraction.py"""

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from src.infrastructure.persistence.local_document_storage import Document, InvalidDocument


@dataclass
class ExtractedText:
    id_documento: str
    nombre_original: str
    texto_extraido: str
    cantidad_caracteres: int
    requiere_ocr: bool
    mensaje: str


def extract_pdf_text(document: Document, path: Path) -> ExtractedText:
    """Lee el original en modo binario de solo lectura."""
    try:
        with path.open("rb") as source:
            reader = PdfReader(source)
            if reader.is_encrypted:
                raise InvalidDocument("El PDF esta cifrado y no se puede extraer su texto.")
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except (PyPdfError, ValueError, OSError) as error:
        raise InvalidDocument("No se pudo extraer texto del PDF: invalido, cifrado o ilegible.") from error
    requires_ocr = not text.strip()
    if requires_ocr:
        text = ""
    return ExtractedText(
        document.id_documento, document.nombre_original, text, len(text), requires_ocr,
        "No se encontro texto extraible; probablemente requiera OCR."
        if requires_ocr else "Texto extraido correctamente.",
    )
