"""src/application/use_cases/document_extraction.py - Extraccion y propuestas."""

from collections.abc import Callable

from src.application.dtos.document_dtos import Document, ExtractedText, ProposedVehicleFields
from src.application.title_field_extraction import extract_title_fields
from src.domain.document_record import DocumentRecord
from src.domain.repositories import DocumentNotFoundError, DocumentRepository


class ExtractDocumentTextUseCase:
    def __init__(
        self,
        load_document: Callable[[str], Document],
        read_text: Callable[[Document], ExtractedText],
    ) -> None:
        self.load_document = load_document
        self.read_text = read_text

    def execute(self, id_documento: str) -> ExtractedText:
        try:
            document = self.load_document(id_documento)
        except FileNotFoundError as error:
            raise DocumentNotFoundError("Documento no encontrado.") from error
        return self.read_text(document)


class ExtractDocumentFieldsUseCase:
    def __init__(
        self,
        extract_text: Callable[[str], ExtractedText],
        repository: DocumentRepository,
    ) -> None:
        self.extract_text = extract_text
        self.repository = repository

    def execute(self, id_documento: str) -> ProposedVehicleFields:
        extracted = self.extract_text(id_documento)
        proposal = extract_title_fields(id_documento, extracted.texto_extraido)
        self.repository.save_pending(
            DocumentRecord(
                id_documento=id_documento,
                nombre_original=extracted.nombre_original,
                patente=proposal.patente,
                marca=proposal.marca,
                modelo=proposal.modelo,
                numero_motor=proposal.numero_motor,
                numero_chasis=proposal.numero_chasis,
                anio=proposal.anio,
            )
        )
        return proposal
