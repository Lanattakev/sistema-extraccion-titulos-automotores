"""src/infrastructure/extraction/scanned_pdf.py - Renderizado PDF y OCR por pagina."""

from collections.abc import Callable
from contextlib import closing
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

from src.application.document_errors import InvalidDocument
from src.application.dtos.document_dtos import Document, ExtractedText
from src.application.text_extraction import TextExtractor, pdf_text_result
from src.infrastructure.extraction.image_ocr import recognize_image_text


class ScannedPdfOcrExtractor(TextExtractor):
    def __init__(self, recognize: Callable[[Image.Image], str] | None = None) -> None:
        self.recognize = recognize if recognize is not None else recognize_image_text

    def read_text(self, path: Path) -> str:
        """Libera una pagina por vez, sin escribir imagenes en disco."""
        texts: list[str] = []
        try:
            with pdfium.PdfDocument(str(path)) as pdf:
                for index in range(len(pdf)):
                    with closing(pdf[index]) as page, closing(page.render(scale=2)) as bitmap:
                        with closing(bitmap.to_pil()) as image:
                            text = self.recognize(image)
                            if text:
                                texts.append(text)
        except (pdfium.PdfiumError, OSError, ValueError, RuntimeError) as error:
            raise InvalidDocument("No se pudo renderizar o realizar OCR del PDF.") from error
        return "\n".join(texts)

    def extract(self, document: Document, path: Path) -> ExtractedText:
        return pdf_text_result(document, self.read_text(path))
