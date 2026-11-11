"""src/infrastructure/document_processing.py - Puente con los originales almacenados."""

from src.application.dtos.document_dtos import Document, ExtractedText
from src.infrastructure.extraction.factory import TextExtractorFactory
from src.infrastructure.persistence import local_document_storage as storage


def read_document_text(
    document: Document,
    factory: TextExtractorFactory | None = None,
) -> ExtractedText:
    if factory is None:
        factory = TextExtractorFactory()
    extractor = factory.create(document.tipo_archivo)
    path = storage.UPLOAD_DIRECTORY / document.nombre_interno
    return extractor.extract(document, path)
