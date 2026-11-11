"""src/application/text_extraction.py - Contrato y politica de fallback PDF."""

from pathlib import Path
from typing import Protocol, runtime_checkable

from src.application.dtos.document_dtos import Document, ExtractedText
from src.application.title_field_extraction import extract_title_fields


@runtime_checkable
class TextExtractor(Protocol):
    """Procesa un original local sin cargar todos sus bytes en memoria.

    Los metadatos permiten conservar los DTOs y contratos HTTP existentes.
    El protocolo no depende de lectores PDF, OCR ni frameworks web.
    """

    def extract(self, document: Document, path: Path) -> ExtractedText: ...


def pdf_text_result(document: Document, text: str) -> ExtractedText:
    requires_ocr = not bool(text)
    return ExtractedText(
        document.id_documento,
        document.nombre_original,
        text,
        len(text),
        requires_ocr,
        "OCR no obtuvo texto util; se requiere revision humana."
        if requires_ocr
        else "Texto extraido correctamente.",
    )


class PdfTextExtractor(TextExtractor):
    """Un solo campo valido en texto directo evita renderizado y OCR."""

    def __init__(self, native: TextExtractor, scanned: TextExtractor) -> None:
        self.native = native
        self.scanned = scanned

    def extract(self, document: Document, path: Path) -> ExtractedText:
        result = self.native.extract(document, path)
        proposal = extract_title_fields(document.id_documento, result.texto_extraido)
        if any(
            value is not None
            for value in (
                proposal.patente,
                proposal.marca,
                proposal.modelo,
                proposal.numero_motor,
                proposal.numero_chasis,
                proposal.anio,
            )
        ):
            return result
        return self.scanned.extract(document, path)
