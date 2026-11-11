"""src/infrastructure/extraction/factory.py - Seleccion extensible por MIME."""

from collections.abc import Mapping

from src.application.document_errors import UnsupportedDocument
from src.application.text_extraction import PdfTextExtractor, TextExtractor
from src.infrastructure.extraction.image_ocr import ImageOcrExtractor
from src.infrastructure.extraction.native_pdf import NativePdfExtractor
from src.infrastructure.extraction.scanned_pdf import ScannedPdfOcrExtractor


class TextExtractorFactory:
    def __init__(self, extractors: Mapping[str, TextExtractor] | None = None) -> None:
        if extractors is None:
            image = ImageOcrExtractor()
            extractors = {
                "application/pdf": PdfTextExtractor(NativePdfExtractor(), ScannedPdfOcrExtractor()),
                "image/jpeg": image,
                "image/png": image,
            }
        self.extractors = dict(extractors)

    def register(self, mime_type: str, extractor: TextExtractor) -> None:
        """Permite agregar formatos o reemplazar motores sin modificar la seleccion."""
        self.extractors[mime_type] = extractor

    def create(self, mime_type: str) -> TextExtractor:
        try:
            return self.extractors[mime_type]
        except KeyError as error:
            raise UnsupportedDocument("Solo se admiten PDF, JPG/JPEG y PNG.") from error
