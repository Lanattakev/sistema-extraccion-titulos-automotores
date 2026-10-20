"""src/infrastructure/extracted_text.py"""

from dataclasses import dataclass


@dataclass
class ExtractedText:
    id_documento: str
    nombre_original: str
    texto_extraido: str
    cantidad_caracteres: int
    requiere_ocr: bool
    mensaje: str
