"""src/infrastructure/fastapi/document_http.py - Multipart y errores del transporte."""

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import HTTPException, Request, Response
from fastapi.routing import APIRoute
from starlette.datastructures import UploadFile

from src.application.document_errors import (
    DocumentTooLarge,
    InvalidDocument,
    InvalidUpload,
    UnsupportedDocument,
)
from src.application.dtos.document_dtos import (
    DocumentUpload,
    RejectedDocumentUpload,
)
from src.domain.repositories import DocumentConflictError, DocumentNotFoundError

DOCUMENT_ERROR_STATUS = {
    InvalidDocument: 400,
    DocumentNotFoundError: 404,
    DocumentConflictError: 409,
    DocumentTooLarge: 413,
    UnsupportedDocument: 415,
    InvalidUpload: 422,
}


def document_error_status(error: Exception) -> int:
    return next(
        code for error_type, code in DOCUMENT_ERROR_STATUS.items() if isinstance(error, error_type)
    )


class DocumentRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def handle(request: Request) -> Response:
            try:
                return await handler(request)
            except (
                InvalidDocument,
                DocumentNotFoundError,
                DocumentConflictError,
                DocumentTooLarge,
                UnsupportedDocument,
                InvalidUpload,
            ) as error:
                status_code = document_error_status(error)
                raise HTTPException(status_code=status_code, detail=str(error)) from error

        return handle


def to_document_upload(file: UploadFile | str) -> DocumentUpload:
    if not isinstance(file, UploadFile):
        raise InvalidUpload("El archivo debe tener nombre.")
    disposition = file.headers.get("content-disposition", "")
    if "\\" in disposition or ":" in disposition:
        raise InvalidDocument("El nombre no puede contener rutas.")
    return DocumentUpload(file.file, file.filename or "")


def to_batch_upload(file: UploadFile | str) -> DocumentUpload | RejectedDocumentUpload:
    try:
        return to_document_upload(file)
    except (InvalidUpload, InvalidDocument) as error:
        name = (file.filename or "") if isinstance(file, UploadFile) else ""
        return RejectedDocumentUpload(name, error)
