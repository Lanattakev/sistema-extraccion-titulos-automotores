"""src/infrastructure/image_text_extraction.py - Compatibilidad del OCR existente.

La implementacion se encuentra en extraction/image_ocr.py.
Se conservan la funcion publica y las referencias usadas por las pruebas existentes.
"""

from pathlib import Path

from src.application.dtos.document_dtos import Document, ExtractedText
from src.infrastructure.extraction.image_ocr import ImageOcrExtractor
from src.infrastructure.extraction.image_ocr import get_settings as get_settings
from src.infrastructure.extraction.image_ocr import (
    pytesseract as pytesseract,
)
from src.infrastructure.extraction.image_ocr import (
    recognize_image_text as recognize_image_text,
)


def extract_image_text(document: Document, path: Path) -> ExtractedText:
    return ImageOcrExtractor().extract(document, path)
