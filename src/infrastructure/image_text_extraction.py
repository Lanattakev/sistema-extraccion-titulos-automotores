"""src/infrastructure/image_text_extraction.py — OCR local de imagenes."""

from pathlib import Path

import pytesseract
from PIL import Image

from src.infrastructure.pdf_text_extraction import ExtractedText
from src.infrastructure.persistence.local_document_storage import Document, InvalidDocument
from src.infrastructure.settings.config import get_settings


def extract_image_text(document: Document, path: Path) -> ExtractedText:
    """Lee una imagen local sin modificarla ni guardar registros de vehiculos."""
    settings = get_settings()
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
    try:
        with Image.open(path) as image:
            if image.format not in {"JPEG", "PNG"}:
                raise InvalidDocument("Solo se admite OCR de imagenes JPG/JPEG y PNG.")
            text = pytesseract.image_to_string(
                image, lang=settings.TESSERACT_LANG, timeout=settings.TESSERACT_TIMEOUT,
            )
    except (OSError, ValueError, RuntimeError, Image.DecompressionBombError) as error:
        raise InvalidDocument(
            "No se pudo realizar OCR: imagen ilegible o Tesseract no disponible."
        ) from error
    if not any(character.isalnum() for character in text):
        text = ""
    return ExtractedText(
        document.id_documento, document.nombre_original, text, len(text), not bool(text),
        "Texto extraido mediante OCR; requiere revision humana."
        if text else "OCR no obtuvo texto util; se requiere revision humana.",
    )
