"""src/domain/document_record.py — Estado persistente del documento."""

from dataclasses import dataclass
from typing import Literal


@dataclass
class DocumentRecord:
    id_documento: str
    nombre_original: str
    patente: str | None = None
    marca: str | None = None
    modelo: str | None = None
    numero_motor: str | None = None
    numero_chasis: str | None = None
    anio: int | None = None
    estado: Literal["pendiente", "revisado", "registrado"] = "pendiente"
    id_interno: str | None = None
