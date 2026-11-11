"""src/application/use_cases/process_batch_documents.py - Lotes sin dependencia HTTP."""

import asyncio
import logging
from collections.abc import Callable, Iterable
from dataclasses import asdict
from typing import BinaryIO

from src.application.document_errors import (
    DocumentTooLarge,
    InvalidDocument,
    InvalidUpload,
    UnsupportedDocument,
)
from src.application.dtos.document_dtos import (
    BatchDocumentResult,
    Document,
    DocumentUpload,
    ProposedVehicleFields,
    RejectedDocumentUpload,
)
from src.domain.repositories import DocumentNotFoundError

logger = logging.getLogger(__name__)


class ProcessBatchDocumentsUseCase:
    def __init__(
        self,
        save_document: Callable[[BinaryIO, str], Document],
        extract_fields: Callable[[str], ProposedVehicleFields],
    ) -> None:
        self.save_document = save_document
        self.extract_fields = extract_fields

    async def execute(
        self,
        uploads: Iterable[DocumentUpload | RejectedDocumentUpload],
    ) -> list[BatchDocumentResult]:
        # Como antes, un archivo a la vez: orden estable y memoria acotada.
        # El trabajo bloqueante se ejecuta fuera del event loop con la biblioteca estandar.
        results = []
        for upload in uploads:
            results.append(await asyncio.to_thread(self.process_file, upload))
        return results

    def process_file(self, upload: DocumentUpload | RejectedDocumentUpload) -> BatchDocumentResult:
        result = BatchDocumentResult(nombre_original=upload.nombre_original)
        try:
            if isinstance(upload, RejectedDocumentUpload):
                raise upload.error
            document = self.save_document(upload.source, upload.nombre_original)
            result.id_documento = document.id_documento
            proposal = self.extract_fields(document.id_documento)
            return BatchDocumentResult(**asdict(proposal), nombre_original=document.nombre_original)
        except (
            InvalidDocument,
            DocumentTooLarge,
            InvalidUpload,
            UnsupportedDocument,
            DocumentNotFoundError,
        ) as error:
            result.error = str(error)
        except Exception:
            logger.exception("Error procesando documento del lote: %s", result.nombre_original)
            result.error = "No se pudo procesar el documento por un error interno."
        result.fallo = True
        return result
