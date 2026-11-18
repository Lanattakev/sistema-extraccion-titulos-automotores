"""src/infrastructure/fastapi/document_content.py - Originales para revision visual."""

from pathlib import Path

from fastapi.responses import FileResponse

from src.domain.repositories import DocumentNotFoundError
from src.infrastructure.persistence import local_document_storage as storage


def document_content_response(document_id: str) -> FileResponse:
    try:
        document = storage.get_document(document_id)
        path = (storage.UPLOAD_DIRECTORY / document.nombre_interno).resolve(strict=True)
        if not path.is_relative_to(storage.UPLOAD_DIRECTORY.resolve()):
            raise FileNotFoundError("Original fuera del almacenamiento documental.")
        file_stat = path.stat()
    except FileNotFoundError as error:
        raise DocumentNotFoundError("Documento no encontrado.") from error
    return FileResponse(
        path,
        media_type=storage.FILE_TYPES[Path(document.nombre_interno).suffix.lower()],
        filename=document.nombre_original,
        content_disposition_type="inline",
        stat_result=file_stat,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )
