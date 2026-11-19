"""src/infrastructure/fastapi/document_dependencies.py - Composicion de casos de uso."""

from typing import Annotated

from fastapi import Depends, Request

from src.application.dtos.document_dtos import Document, ProposedVehicleFields
from src.application.title_field_extraction import extract_title_fields
from src.application.use_cases.document_extraction import (
    ExtractDocumentFieldsUseCase,
    ExtractDocumentTextUseCase,
)
from src.application.use_cases.document_workflow import (
    ConfirmDocumentUseCase,
    ReviewDocumentUseCase,
    UploadDocumentUseCase,
)
from src.application.use_cases.process_batch_documents import ProcessBatchDocumentsUseCase
from src.domain.repositories import DocumentRepository
from src.infrastructure.batch_processing import BatchDocumentProcessor
from src.infrastructure.document_processing import read_document_text
from src.infrastructure.persistence import local_document_storage as storage


def get_document_repository(request: Request) -> DocumentRepository:
    return request.app.state.document_repository


Repository = Annotated[DocumentRepository, Depends(get_document_repository)]


def get_text_use_case() -> ExtractDocumentTextUseCase:
    return ExtractDocumentTextUseCase(storage.get_document, read_document_text)


TextUseCase = Annotated[ExtractDocumentTextUseCase, Depends(get_text_use_case)]


def get_fields_use_case(repository: Repository, text: TextUseCase) -> ExtractDocumentFieldsUseCase:
    return ExtractDocumentFieldsUseCase(text.execute, repository)


def get_upload_use_case(repository: Repository) -> UploadDocumentUseCase:
    return UploadDocumentUseCase(storage.save_document, repository)


def get_review_use_case(repository: Repository) -> ReviewDocumentUseCase:
    return ReviewDocumentUseCase(repository)


def get_confirm_use_case(repository: Repository) -> ConfirmDocumentUseCase:
    return ConfirmDocumentUseCase(repository)


def get_batch_use_case(
    request: Request,
    fields: Annotated[ExtractDocumentFieldsUseCase, Depends(get_fields_use_case)],
) -> ProcessBatchDocumentsUseCase:
    processor: BatchDocumentProcessor = request.app.state.batch_processor

    async def process_saved(document: Document) -> ProposedVehicleFields:
        text = await processor.extract(document, storage.UPLOAD_DIRECTORY / document.nombre_interno)
        # La persistencia se realiza luego, por indice, en el caso de uso del lote.
        return extract_title_fields(document.id_documento, text.texto_extraido)

    return ProcessBatchDocumentsUseCase(
        storage.save_document,
        fields.execute,
        process_saved=process_saved,
        parallelism=processor.max_workers,
        save_pending=fields.repository.save_pending,
    )
