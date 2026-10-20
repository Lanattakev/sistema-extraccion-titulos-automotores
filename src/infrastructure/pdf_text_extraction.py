"""src/infrastructure/pdf_text_extraction.py"""

from contextlib import closing
from pathlib import Path

import pypdfium2 as pdfium
from pypdf import PdfReader
from pypdf.errors import PyPdfError

from src.application.title_field_extraction import extract_title_fields
from src.infrastructure.extracted_text import ExtractedText
from src.infrastructure.image_text_extraction import recognize_image_text
from src.infrastructure.persistence.local_document_storage import Document, InvalidDocument


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
    proposal = extract_title_fields(document.id_documento, text)
    # Un solo campo valido basta; no exigimos que el titulo este completo.
    requires_ocr = not any(value is not None for value in (
        proposal.patente, proposal.marca, proposal.modelo,
        proposal.numero_motor, proposal.numero_chasis, proposal.anio,
    ))
    if requires_ocr:
        text = extract_scanned_pdf_text(path)
        requires_ocr = not bool(text)
    return ExtractedText(
        document.id_documento, document.nombre_original, text, len(text), requires_ocr,
        "OCR no obtuvo texto util; se requiere revision humana."
        if requires_ocr else "Texto extraido correctamente.",
    )


def extract_scanned_pdf_text(path: Path) -> str:
    """Renderiza y libera una pagina a la vez; no escribe imagenes en disco."""
    texts: list[str] = []
    try:
        with pdfium.PdfDocument(str(path)) as pdf:
            for index in range(len(pdf)):
                with closing(pdf[index]) as page, closing(page.render(scale=2)) as bitmap:
                    with bitmap.to_pil() as image:
                        text = recognize_image_text(image)
                        if text:
                            texts.append(text)
    except (pdfium.PdfiumError, OSError, ValueError, RuntimeError) as error:
        raise InvalidDocument("No se pudo renderizar o realizar OCR del PDF.") from error
    return "\n".join(texts)
