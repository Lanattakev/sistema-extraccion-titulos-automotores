"""src/infrastructure/fastapi/routers/documents.py - Transporte HTTP documental."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from starlette.concurrency import run_in_threadpool

from src.application.dtos.document_dtos import (
    BatchDocumentResult,
    Document,
    ExtractedText,
    ProposedVehicleFields,
)
from src.application.dtos.vehicle_dtos import ReviewedVehicleRequest
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
from src.domain.document_record import DocumentRecord
from src.domain.vehicle_record import VehicleIntake
from src.infrastructure.fastapi.document_dependencies import (
    Repository as DocumentRepository,
)
from src.infrastructure.fastapi.document_dependencies import (
    get_batch_use_case,
    get_confirm_use_case,
    get_fields_use_case,
    get_review_use_case,
    get_text_use_case,
    get_upload_use_case,
)
from src.infrastructure.fastapi.document_dependencies import (
    get_document_repository as get_document_repository,
)
from src.infrastructure.fastapi.document_http import (
    DocumentRoute,
    to_batch_upload,
    to_document_upload,
)

router = APIRouter(prefix="/documents", tags=["Documents"], route_class=DocumentRoute)


@router.get("", response_model=list[DocumentRecord])
def list_documents(repository: DocumentRepository) -> list[DocumentRecord]:
    return repository.list_all()


@router.patch("/{id_documento}/review", response_model=DocumentRecord)
def review_document(
    id_documento: str,
    payload: ReviewedVehicleRequest,
    use_case: Annotated[ReviewDocumentUseCase, Depends(get_review_use_case)],
) -> DocumentRecord:
    return use_case.execute(id_documento, payload)


@router.post(
    "/batch",
    response_model=list[BatchDocumentResult],
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["files"],
                        "properties": {
                            "files": {
                                "type": "array",
                                "items": {"type": "string", "format": "binary"},
                            }
                        },
                    }
                }
            },
        }
    },
)
async def create_document_batch(
    request: Request,
    use_case: Annotated[ProcessBatchDocumentsUseCase, Depends(get_batch_use_case)],
) -> list[BatchDocumentResult]:
    async with request.form(max_files=100, max_fields=0) as form:
        entries = form.multi_items()
        if not entries or any(key != "files" for key, _ in entries):
            raise HTTPException(status_code=422, detail="Debe enviar archivos en files.")
        return await use_case.execute(to_batch_upload(file) for _, file in entries)


@router.post(
    "/{id_documento}/confirm", response_model=VehicleIntake, status_code=status.HTTP_201_CREATED
)
def confirm_document(
    id_documento: str,
    payload: ReviewedVehicleRequest,
    use_case: Annotated[ConfirmDocumentUseCase, Depends(get_confirm_use_case)],
) -> VehicleIntake:
    return use_case.execute(id_documento, payload)


@router.post("/{id_documento}/extract-fields", response_model=ProposedVehicleFields)
def extract_document_fields(
    id_documento: str,
    use_case: Annotated[ExtractDocumentFieldsUseCase, Depends(get_fields_use_case)],
) -> ProposedVehicleFields:
    return use_case.execute(id_documento)


@router.post("/{id_documento}/extract-text", response_model=ExtractedText)
def extract_document_text(
    id_documento: str,
    use_case: Annotated[ExtractDocumentTextUseCase, Depends(get_text_use_case)],
) -> ExtractedText:
    return use_case.execute(id_documento)


@router.post(
    "",
    response_model=Document,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["file"],
                        "properties": {"file": {"type": "string", "format": "binary"}},
                    }
                }
            },
        }
    },
)
async def create_document(
    request: Request,
    use_case: Annotated[UploadDocumentUseCase, Depends(get_upload_use_case)],
) -> Document:
    async with request.form(max_files=1, max_fields=0) as form:
        entries = form.multi_items()
        if len(entries) != 1 or entries[0][0] != "file":
            raise HTTPException(status_code=422, detail="Debe enviar un solo archivo en file.")
        return await run_in_threadpool(use_case.execute, to_document_upload(entries[0][1]))
