"""src/infrastructure/document_processing.py - Adaptacion de motores existentes."""

from src.application.document_errors import UnsupportedDocument
from src.application.dtos.document_dtos import Document, ExtractedText
from src.infrastructure.image_text_extraction import extract_image_text
from src.infrastructure.pdf_text_extraction import extract_pdf_text
from src.infrastructure.persistence import local_document_storage as storage


def read_document_text(document: Document) -> ExtractedText:
    # Se conserva la seleccion existente. Strategy/Factory corresponde al issue #4.
    extractors = {
        "application/pdf": extract_pdf_text,
        "image/jpeg": extract_image_text,
        "image/png": extract_image_text,
    }
    extractor = extractors.get(document.tipo_archivo)
    if extractor is None:
        raise UnsupportedDocument("Solo se admiten PDF, JPG/JPEG y PNG.")
    return extractor(document, storage.UPLOAD_DIRECTORY / document.nombre_interno)
