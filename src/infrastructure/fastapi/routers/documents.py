"""src/infrastructure/fastapi/routers/documents.py"""

import logging
from dataclasses import asdict, dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from src.application.title_field_extraction import ProposedVehicleFields, extract_title_fields
from src.domain.document_record import DocumentRecord
from src.domain.vehicle_record import VehicleIntake
from src.infrastructure.fastapi.routers.vehicles import ReviewedVehicleRequest
from src.infrastructure.image_text_extraction import extract_image_text
from src.infrastructure.pdf_text_extraction import ExtractedText, extract_pdf_text
from src.infrastructure.persistence import local_document_storage as storage
from src.infrastructure.persistence.local_document_storage import (
    Document,
    DocumentTooLarge,
    InvalidDocument,
    save_document,
)
from src.infrastructure.persistence.sqlite_document_repository import (
    DocumentConflictError,
    DocumentNotFoundError,
    SQLiteDocumentRepository,
)

router = APIRouter(prefix="/documents", tags=["Documents"])
logger = logging.getLogger(__name__)


def get_document_repository(request: Request) -> SQLiteDocumentRepository:
    return request.app.state.document_repository


DocumentRepository = Annotated[SQLiteDocumentRepository, Depends(get_document_repository)]


@router.get("", response_model=list[DocumentRecord])
def list_documents(repository: DocumentRepository) -> list[DocumentRecord]:
    return repository.list_all()


@router.patch("/{id_documento}/review", response_model=DocumentRecord)
def review_document(id_documento: str, payload: ReviewedVehicleRequest,
                    repository: DocumentRepository) -> DocumentRecord:
    try:
        return repository.review(id_documento, payload.to_vehicle())
    except DocumentNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except DocumentConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@dataclass
class BatchDocumentResult(ProposedVehicleFields):
    id_documento: str | None = None
    requiere_revision: bool = False
    nombre_original: str = ""
    fallo: bool = False
    error: str | None = None


@router.post("/batch", response_model=list[BatchDocumentResult], openapi_extra={
    "requestBody": {"required": True, "content": {"multipart/form-data": {
        "schema": {"type": "object", "required": ["files"], "properties": {
            "files": {"type": "array", "items": {"type": "string", "format": "binary"}}
        }}
    }}}
})
async def create_document_batch(request: Request, repository: DocumentRepository) -> list[BatchDocumentResult]:
    async with request.form(max_files=100, max_fields=0) as form:
        entries = form.multi_items()
        if not entries or any(key != "files" for key, _ in entries):
            raise HTTPException(status_code=422, detail="Debe enviar archivos en files.")
        results = []
        for _, file in entries:
            results.append(await process_batch_file(file, repository))
        return results


async def process_batch_file(file: UploadFile | str, repository: SQLiteDocumentRepository) -> BatchDocumentResult:
    result = BatchDocumentResult(
        nombre_original=(file.filename or "") if isinstance(file, UploadFile) else "",
    )
    try:
        document = await store_uploaded_document(file)
        result.id_documento = document.id_documento
        proposal = await run_in_threadpool(extract_document_fields, document.id_documento, repository)
        return BatchDocumentResult(
            id_documento=document.id_documento,
            nombre_original=document.nombre_original,
            patente=proposal.patente,
            marca=proposal.marca,
            modelo=proposal.modelo,
            numero_motor=proposal.numero_motor,
            numero_chasis=proposal.numero_chasis,
            anio=proposal.anio,
            requiere_revision=True,
            fallo=False,
            error=None,
        )
    except HTTPException as error:
        result.error = str(error.detail)
    except Exception:
        logger.exception("Error procesando documento del lote: %s", result.nombre_original)
        result.error = "No se pudo procesar el documento por un error interno."
    result.fallo = True
    return result


@router.post("/{id_documento}/confirm", response_model=VehicleIntake,
             status_code=status.HTTP_201_CREATED)
def confirm_document(
    id_documento: str, payload: ReviewedVehicleRequest, repository: DocumentRepository,
) -> VehicleIntake:
    try:
        return repository.confirm(id_documento, payload.to_vehicle())
    except DocumentNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except DocumentConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


def get_document_or_error(id_documento: str) -> Document:
    try:
        return storage.get_document(id_documento)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Documento no encontrado.") from error
    except InvalidDocument as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/{id_documento}/extract-fields", response_model=ProposedVehicleFields)
def extract_document_fields(id_documento: str, repository: DocumentRepository) -> ProposedVehicleFields:
    extracted = extract_document_text(id_documento)
    proposal = extract_title_fields(id_documento, extracted.texto_extraido)
    fields = asdict(proposal)
    fields.pop("requiere_revision")
    repository.save_pending(DocumentRecord(nombre_original=extracted.nombre_original, **fields))
    return proposal


@router.post("/{id_documento}/extract-text", response_model=ExtractedText)
def extract_document_text(id_documento: str) -> ExtractedText:
    document = get_document_or_error(id_documento)
    extractors = {
        "application/pdf": extract_pdf_text,
        "image/jpeg": extract_image_text,
        "image/png": extract_image_text,
    }
    extractor = extractors.get(document.tipo_archivo)
    if extractor is None:
        raise HTTPException(status_code=415, detail="Solo se admiten PDF, JPG/JPEG y PNG.")
    try:
        return extractor(document, storage.UPLOAD_DIRECTORY / document.nombre_interno)
    except InvalidDocument as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("", response_model=Document, status_code=status.HTTP_201_CREATED,
             openapi_extra={"requestBody": {"required": True, "content": {
                 "multipart/form-data": {"schema": {"type": "object", "required": ["file"],
                     "properties": {"file": {"type": "string", "format": "binary"}}}}
             }}})
async def create_document(request: Request, repository: DocumentRepository) -> Document:
    async with request.form(max_files=1, max_fields=0) as form:
        entries = form.multi_items()
        if len(entries) != 1 or entries[0][0] != "file":
            raise HTTPException(status_code=422, detail="Debe enviar un solo archivo en file.")
        document = await store_uploaded_document(entries[0][1])
        await run_in_threadpool(repository.save_pending, DocumentRecord(
            id_documento=document.id_documento, nombre_original=document.nombre_original,
        ))
        return document


async def store_uploaded_document(file: UploadFile | str) -> Document:
    if not isinstance(file, UploadFile):
        raise HTTPException(status_code=422, detail="El archivo debe tener nombre.")
    disposition = file.headers.get("content-disposition", "")
    if "\\" in disposition or ":" in disposition:
        raise HTTPException(status_code=400, detail="El nombre no puede contener rutas.")
    try:
        return await run_in_threadpool(save_document, file.file, file.filename or "")
    except InvalidDocument as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except DocumentTooLarge as error:
        raise HTTPException(status_code=413, detail=str(error)) from error
