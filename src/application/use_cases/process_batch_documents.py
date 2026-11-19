"""src/application/use_cases/process_batch_documents.py - Lotes sin dependencia HTTP."""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable
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
from src.domain.document_record import DocumentRecord
from src.domain.repositories import DocumentNotFoundError

logger = logging.getLogger(__name__)


class ProcessBatchDocumentsUseCase:
    def __init__(
        self,
        save_document: Callable[[BinaryIO, str], Document],
        extract_fields: Callable[[str], ProposedVehicleFields],
        *,
        process_saved: Callable[[Document], Awaitable[ProposedVehicleFields]] | None = None,
        parallelism: int = 1,
        save_pending: Callable[[DocumentRecord], None] | None = None,
    ) -> None:
        if parallelism < 1:
            raise ValueError("El paralelismo del lote debe ser positivo.")
        self.save_document = save_document
        self.extract_fields = extract_fields
        self.process_saved = process_saved
        self.parallelism = parallelism
        self.save_pending = save_pending

    async def execute(
        self,
        uploads: Iterable[DocumentUpload | RejectedDocumentUpload],
    ) -> list[BatchDocumentResult]:
        indexed = iter(enumerate(uploads))
        results: dict[int, BatchDocumentResult] = {}
        stopped = False
        next_to_store = 0
        store_order = asyncio.Condition()

        async def consume() -> None:
            nonlocal next_to_store
            while not stopped:
                item = next(indexed, None)
                if item is None:
                    break
                index, upload = item
                result = await self._process_file(upload)
                async with store_order:
                    while index != next_to_store:
                        await store_order.wait()
                    results[index] = await asyncio.to_thread(self._store_result, result)
                    next_to_store += 1
                    store_order.notify_all()

        tasks = [asyncio.create_task(consume()) for _ in range(self.parallelism)]
        try:
            await asyncio.shield(asyncio.gather(*tasks))
        except BaseException:
            # Drenar archivos en curso antes de cerrar el multipart; no iniciar otros.
            stopped = True
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        return [results[index] for index in sorted(results)]

    def _store_result(self, result: BatchDocumentResult) -> BatchDocumentResult:
        if self.save_pending is None or result.fallo or result.id_documento is None:
            return result
        try:
            self.save_pending(
                DocumentRecord(
                    id_documento=result.id_documento,
                    nombre_original=result.nombre_original,
                    patente=result.patente,
                    marca=result.marca,
                    modelo=result.modelo,
                    numero_motor=result.numero_motor,
                    numero_chasis=result.numero_chasis,
                    anio=result.anio,
                )
            )
        except Exception:
            logger.exception("Error persistiendo documento del lote: %s", result.nombre_original)
            return BatchDocumentResult(
                id_documento=result.id_documento,
                nombre_original=result.nombre_original,
                fallo=True,
                error="No se pudo procesar el documento por un error interno.",
            )
        return result

    async def _process_file(
        self, upload: DocumentUpload | RejectedDocumentUpload
    ) -> BatchDocumentResult:
        result = BatchDocumentResult(nombre_original=upload.nombre_original)
        try:
            if isinstance(upload, RejectedDocumentUpload):
                raise upload.error
            document = await asyncio.to_thread(
                self.save_document, upload.source, upload.nombre_original
            )
            result.id_documento = document.id_documento
            proposal = (
                await self.process_saved(document)
                if self.process_saved is not None
                else await asyncio.to_thread(self.extract_fields, document.id_documento)
            )
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
