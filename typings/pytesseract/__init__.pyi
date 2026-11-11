"""Superficie de pytesseract 0.3.13 utilizada por el proyecto; salida STRING."""

from typing import Literal, Protocol

from PIL.Image import Image

class _TesseractModule(Protocol):
    tesseract_cmd: str

pytesseract: _TesseractModule

def image_to_string(
    image: Image,
    lang: str | None = None,
    config: str = "",
    nice: int = 0,
    output_type: Literal["string"] = "string",
    timeout: int = 0,
) -> str: ...
