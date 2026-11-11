"""src/infrastructure/extraction/image_ocr.py - OCR local de imagenes."""

from collections.abc import Callable
from contextlib import closing
from pathlib import Path

import pytesseract
from PIL import Image

from src.application.document_errors import InvalidDocument
from src.application.dtos.document_dtos import Document, ExtractedText
from src.application.text_extraction import TextExtractor
from src.infrastructure.settings.config import get_settings


def recognize_image_text(image: Image.Image) -> str:
    """OCR compartido por imagenes y paginas PDF; conserva configuracion y timeout."""
    settings = get_settings()
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
    text = pytesseract.image_to_string(
        image,
        lang=settings.TESSERACT_LANG,
        timeout=settings.TESSERACT_TIMEOUT,
    )
    return text if any(character.isalnum() for character in text) else ""


class ImageOcrExtractor(TextExtractor):
    def __init__(self, recognize: Callable[[Image.Image], str] | None = None) -> None:
        self.recognize = recognize if recognize is not None else recognize_image_text

    def extract(self, document: Document, path: Path) -> ExtractedText:
        try:
            with closing(Image.open(path)) as image:
                if image.format not in {"JPEG", "PNG"}:
                    raise InvalidDocument("Solo se admite OCR de imagenes JPG/JPEG y PNG.")
                text = self.recognize(image)
        except (OSError, ValueError, RuntimeError, Image.DecompressionBombError) as error:
            raise InvalidDocument(
                "No se pudo realizar OCR: imagen ilegible o Tesseract no disponible."
            ) from error
        return ExtractedText(
            document.id_documento,
            document.nombre_original,
            text,
            len(text),
            not bool(text),
            "Texto extraido mediante OCR; requiere revision humana."
            if text
            else "OCR no obtuvo texto util; se requiere revision humana.",
        )
