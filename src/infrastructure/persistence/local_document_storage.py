"""src/infrastructure/persistence/local_document_storage.py"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import BinaryIO
from uuid import UUID, uuid4


@dataclass
class Document:
    id_documento: str
    nombre_original: str
    nombre_interno: str
    tipo_archivo: str
    tamanio_bytes: int

UPLOAD_DIRECTORY = Path(__file__).resolve().parents[3] / "uploads"
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
FILE_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


class InvalidDocument(ValueError):
    """Nombre, extension o contenido vacio no admitidos."""


class DocumentTooLarge(ValueError):
    """El documento supera el limite permitido."""


def get_document(document_id: str) -> Document:
    """Busca los metadatos por UUID sin aceptar rutas del cliente."""
    try:
        if str(UUID(document_id)) != document_id:
            raise ValueError("UUID no canonico")
    except ValueError as error:
        raise FileNotFoundError("Documento no encontrado.") from error
    metadata_path = UPLOAD_DIRECTORY / (document_id + ".json")
    document = Document(**json.loads(metadata_path.read_text(encoding="utf-8")))
    extension = Path(document.nombre_original).suffix.lower()
    if document.nombre_interno != document_id + extension or extension not in FILE_TYPES:
        raise InvalidDocument("Los metadatos del documento no son validos.")
    if not (UPLOAD_DIRECTORY / document.nombre_interno).is_file():
        raise FileNotFoundError("Documento no encontrado.")
    return document


def validate_filename(original_name: str) -> str:
    """Valida el nombre sin utilizarlo como ruta."""
    if not original_name or not original_name.strip():
        raise InvalidDocument("El archivo debe tener nombre.")
    if any(character in original_name for character in ("/", "\\", ":", "\x00")):
        raise InvalidDocument("El nombre del archivo no puede contener rutas.")
    extension = Path(original_name).suffix.lower()
    if extension not in FILE_TYPES:
        raise InvalidDocument("Solo se permiten archivos PDF, JPG/JPEG y PNG.")
    return extension


def save_document(source: BinaryIO, original_name: str) -> Document:
    """Copia bytes opacos con nombre generado y creacion exclusiva."""
    extension = validate_filename(original_name)
    document_id = str(uuid4())
    internal_name = document_id + extension
    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    destination = UPLOAD_DIRECTORY / internal_name
    metadata_path = UPLOAD_DIRECTORY / (document_id + ".json")
    size = 0
    # Abrir fuera del try evita eliminar un archivo preexistente ante una colision.
    output = destination.open("xb")
    metadata_created = False
    try:
        with output:
            size = copy_document(source, output)
        if size == 0:
            raise InvalidDocument("El archivo esta vacio.")
        document = Document(document_id, original_name, internal_name, FILE_TYPES[extension], size)
        with metadata_path.open("x", encoding="utf-8") as metadata:
            metadata_created = True
            json.dump(asdict(document), metadata, ensure_ascii=False)
        return document
    except BaseException:
        destination.unlink(missing_ok=True)
        if metadata_created:
            metadata_path.unlink(missing_ok=True)
        raise


def copy_document(source: BinaryIO, output: BinaryIO) -> int:
    """Copia bytes con memoria acotada y limite de tamanio."""
    size = 0
    while chunk := source.read(64 * 1024):
        size += len(chunk)
        if size > MAX_DOCUMENT_BYTES:
            raise DocumentTooLarge("El archivo supera el limite de 10 MiB.")
        output.write(chunk)
    return size
