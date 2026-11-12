"""src/application/dtos/document_dtos.py - Datos de carga, extraccion y lote."""

from dataclasses import dataclass
from typing import BinaryIO, Literal

from src.application.document_errors import InvalidDocument, InvalidUpload


@dataclass
class Document:
    id_documento: str
    nombre_original: str
    nombre_interno: str
    tipo_archivo: str
    tamanio_bytes: int


@dataclass
class ExtractedText:
    id_documento: str
    nombre_original: str
    texto_extraido: str
    cantidad_caracteres: int
    requiere_ocr: bool
    mensaje: str


@dataclass
class ProposedVehicleFields:
    id_documento: str
    patente: str | None = None
    marca: str | None = None
    modelo: str | None = None
    numero_motor: str | None = None
    numero_chasis: str | None = None
    anio: int | None = None
    requiere_revision: Literal[True] = True


@dataclass
class BatchDocumentResult:
    # Un fallo puede no tener ID ni requerir revision: no es una propuesta valida.
    id_documento: str | None = None
    patente: str | None = None
    marca: str | None = None
    modelo: str | None = None
    numero_motor: str | None = None
    numero_chasis: str | None = None
    anio: int | None = None
    requiere_revision: bool = False
    nombre_original: str = ""
    fallo: bool = False
    error: str | None = None


@dataclass
class DocumentUpload:
    source: BinaryIO
    nombre_original: str


@dataclass
class RejectedDocumentUpload:
    nombre_original: str
    error: InvalidDocument | InvalidUpload
