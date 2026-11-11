"""src/infrastructure/extracted_text.py - Compatibilidad del resultado de extraccion.

La definicion del DTO pertenece a la capa de aplicacion.
Este modulo conserva el import utilizado por los motores PDF y OCR.
La reexportacion referencia la misma clase, sin conversiones ni copias.
Los nombres de campos y los valores devueltos por los motores se conservan.
El DTO no conoce rutas, lectores PDF, Tesseract ni detalles de FastAPI.
Los nuevos consumidores pueden importarlo directamente desde application.dtos.
"""

from src.application.dtos.document_dtos import (
    ExtractedText as ExtractedText,
)
