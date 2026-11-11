"""src/infrastructure/pdf_text_extraction.py - Compatibilidad de las funciones PDF."""

from pathlib import Path

from src.application.dtos.document_dtos import Document, ExtractedText
from src.application.text_extraction import PdfTextExtractor
from src.infrastructure.extraction.native_pdf import NativePdfExtractor
from src.infrastructure.extraction.scanned_pdf import ScannedPdfOcrExtractor
from src.infrastructure.extraction.scanned_pdf import pdfium as pdfium


def extract_pdf_text(document: Document, path: Path) -> ExtractedText:
    pipeline = PdfTextExtractor(NativePdfExtractor(), ScannedPdfOcrExtractor())
    return pipeline.extract(document, path)


def extract_scanned_pdf_text(path: Path) -> str:
    return ScannedPdfOcrExtractor().read_text(path)
