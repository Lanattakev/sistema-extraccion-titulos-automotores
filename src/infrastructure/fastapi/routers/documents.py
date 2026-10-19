"""src/infrastructure/fastapi/routers/documents.py"""

from fastapi import APIRouter, HTTPException, Request, status
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from src.application.title_field_extraction import ProposedVehicleFields, extract_title_fields
from src.infrastructure.image_text_extraction import extract_image_text
from src.infrastructure.pdf_text_extraction import ExtractedText, extract_pdf_text
from src.infrastructure.persistence import local_document_storage as storage
from src.infrastructure.persistence.local_document_storage import (
    Document,
    DocumentTooLarge,
    InvalidDocument,
    save_document,
)

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/{id_documento}/extract-fields", response_model=ProposedVehicleFields)
def extract_document_fields(id_documento: str) -> ProposedVehicleFields:
    extracted = extract_document_text(id_documento)
    return extract_title_fields(id_documento, extracted.texto_extraido)


@router.post("/{id_documento}/extract-text", response_model=ExtractedText)
def extract_document_text(id_documento: str) -> ExtractedText:
    try:
        document = storage.get_document(id_documento)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Documento no encontrado.") from error
    except InvalidDocument as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
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
async def create_document(request: Request) -> Document:
    async with request.form(max_files=1, max_fields=0) as form:
        entries = form.multi_items()
        if len(entries) != 1 or entries[0][0] != "file":
            raise HTTPException(status_code=422, detail="Debe enviar un solo archivo en file.")
        file = entries[0][1]
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
