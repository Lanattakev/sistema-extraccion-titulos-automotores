"""src/infrastructure/extraction/native_pdf.py - Texto digital con pypdf."""

from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from src.application.document_errors import InvalidDocument
from src.application.dtos.document_dtos import Document, ExtractedText
from src.application.text_extraction import TextExtractor, pdf_text_result


class NativePdfExtractor(TextExtractor):
    def extract(self, document: Document, path: Path) -> ExtractedText:
        try:
            with path.open("rb") as source:
                reader = PdfReader(source)
                if reader.is_encrypted:
                    raise InvalidDocument("El PDF esta cifrado y no se puede extraer su texto.")
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except (PyPdfError, ValueError, OSError) as error:
            raise InvalidDocument(
                "No se pudo extraer texto del PDF: invalido, cifrado o ilegible."
            ) from error
        return pdf_text_result(document, text)
