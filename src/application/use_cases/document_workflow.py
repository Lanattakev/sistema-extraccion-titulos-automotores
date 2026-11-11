"""src/application/use_cases/document_workflow.py - Carga, revision y confirmacion."""

from collections.abc import Callable
from typing import BinaryIO

from src.application.dtos.document_dtos import Document, DocumentUpload
from src.application.dtos.vehicle_dtos import ReviewedVehicleRequest
from src.domain.document_record import DocumentRecord
from src.domain.repositories import DocumentRepository
from src.domain.vehicle_record import VehicleIntake


class UploadDocumentUseCase:
    def __init__(
        self,
        save_document: Callable[[BinaryIO, str], Document],
        repository: DocumentRepository,
    ) -> None:
        self.save_document = save_document
        self.repository = repository

    def execute(self, upload: DocumentUpload) -> Document:
        document = self.save_document(upload.source, upload.nombre_original)
        self.repository.save_pending(
            DocumentRecord(
                id_documento=document.id_documento,
                nombre_original=document.nombre_original,
            )
        )
        return document


class ReviewDocumentUseCase:
    def __init__(self, repository: DocumentRepository) -> None:
        self.repository = repository

    def execute(self, id_documento: str, payload: ReviewedVehicleRequest) -> DocumentRecord:
        return self.repository.review(id_documento, payload.to_vehicle())


class ConfirmDocumentUseCase:
    def __init__(self, repository: DocumentRepository) -> None:
        self.repository = repository

    def execute(self, id_documento: str, payload: ReviewedVehicleRequest) -> VehicleIntake:
        # La transaccion completa sigue siendo responsabilidad del repositorio.
        return self.repository.confirm(id_documento, payload.to_vehicle())
