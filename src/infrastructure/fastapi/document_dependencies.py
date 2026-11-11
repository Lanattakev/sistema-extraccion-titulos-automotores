"""src/infrastructure/fastapi/document_dependencies.py - Composicion de casos de uso."""

from typing import Annotated

from fastapi import Depends, Request

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
    fields: Annotated[ExtractDocumentFieldsUseCase, Depends(get_fields_use_case)],
) -> ProcessBatchDocumentsUseCase:
    return ProcessBatchDocumentsUseCase(storage.save_document, fields.execute)
