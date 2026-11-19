"""src/infrastructure/batch_processing.py - Extraccion CPU en procesos sin SQLite."""

import asyncio
import logging
import multiprocessing
from collections.abc import Awaitable
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from src.application.dtos.document_dtos import Document, ExtractedText
from src.infrastructure.extraction.factory import TextExtractorFactory
from src.infrastructure.extraction.image_ocr import recognize_image_text
from src.infrastructure.settings.config import Settings, batch_cpu_limit, initialize_batch_worker

logger = logging.getLogger(__name__)


async def _drain_on_cancel(work: Awaitable[ExtractedText]) -> ExtractedText:
    pending = asyncio.ensure_future(work)
    try:
        return await asyncio.shield(pending)
    except asyncio.CancelledError:
        await asyncio.gather(pending, return_exceptions=True)
        raise


@dataclass(frozen=True)
class BatchExtractionJob:
    document: Document
    path: str
    command: str
    language: str
    timeout: int


def extract_batch_text(job: BatchExtractionJob) -> ExtractedText:
    """Funcion importable para spawn; no recibe uploads, repositorios ni conexiones."""
    settings = Settings(
        TESSERACT_CMD=job.command,
        TESSERACT_LANG=job.language,
        TESSERACT_TIMEOUT=job.timeout,
    )
    recognize = partial(recognize_image_text, settings=settings)
    extractor = TextExtractorFactory(recognize=recognize).create(job.document.tipo_archivo)
    return extractor.extract(job.document, Path(job.path))


class BatchDocumentProcessor:
    """Pool por lifespan con admision global acotada y fallback serial de solo lectura."""

    def __init__(self, settings: Settings) -> None:
        self.max_workers = min(
            settings.BATCH_MAX_WORKERS, batch_cpu_limit(), settings.BATCH_MEMORY_BUDGET_MB // 256
        )
        self._ocr = (settings.TESSERACT_CMD, settings.TESSERACT_LANG, settings.TESSERACT_TIMEOUT)
        self._slots = asyncio.Semaphore(self.max_workers)
        self._serial = asyncio.Lock()
        self._pool: ProcessPoolExecutor | None = None
        self._failed = False
        self._closed = False

    async def extract(self, document: Document, path: Path) -> ExtractedText:
        job = BatchExtractionJob(document, str(path.resolve()), *self._ocr)
        async with self._slots:
            if self._closed:
                raise RuntimeError("El procesador de lotes esta cerrado.")
            if self.max_workers > 1 and not self._failed:
                try:
                    if self._pool is None:
                        self._pool = ProcessPoolExecutor(
                            max_workers=self.max_workers,
                            mp_context=multiprocessing.get_context("spawn"),
                            initializer=initialize_batch_worker,
                        )
                    pending = asyncio.get_running_loop().run_in_executor(
                        self._pool, extract_batch_text, job
                    )
                except (OSError, RuntimeError):
                    self._failed = True
                    logger.warning(
                        "Pool no disponible; fallback secuencial del lote.", exc_info=True
                    )
                else:
                    try:
                        return await _drain_on_cancel(pending)
                    except BrokenProcessPool:
                        self._failed = True
                        logger.warning(
                            "Pool interrumpido; fallback secuencial del lote.", exc_info=True
                        )
            async with self._serial:
                return await _drain_on_cancel(asyncio.to_thread(extract_batch_text, job))

    async def close(self) -> None:
        self._closed = True
        if self._pool is not None:
            await asyncio.to_thread(self._pool.shutdown, wait=True, cancel_futures=True)
