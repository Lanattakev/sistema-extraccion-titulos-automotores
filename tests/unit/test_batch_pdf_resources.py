"""tests/unit/test_batch_pdf_resources.py - Liberacion previa a cada pagina y al error."""

from unittest.mock import Mock

import pytest
from PIL import Image

from src.application.document_errors import InvalidDocument
from src.application.dtos.document_dtos import Document
from src.infrastructure.extraction import scanned_pdf


@pytest.mark.parametrize("fail", [False, True])
def test_page_bitmap_and_image_closed_before_next_page_or_response(monkeypatch, tmp_path, fail):
    images, pages, bitmaps = [], [], []
    closed_pages = []
    pdf = Mock()
    pdf.__enter__ = Mock(return_value=pdf)
    pdf.__exit__ = Mock(return_value=False)
    pdf.__len__ = Mock(return_value=2)

    def page_at(index):
        if index:
            assert closed_pages == [0]
        image = Image.new("RGB", (10, 10))
        images.append(image)
        bitmap = Mock()
        bitmap.to_pil.return_value = image

        def close_bitmap():
            with pytest.raises(ValueError):
                image.getpixel((0, 0))

        bitmap.close.side_effect = close_bitmap
        page = Mock()
        page.render.return_value = bitmap

        def close_page():
            bitmap.close.assert_called_once()
            closed_pages.append(index)

        page.close.side_effect = close_page
        pages.append(page)
        bitmaps.append(bitmap)
        return page

    pdf.__getitem__ = Mock(side_effect=page_at)
    monkeypatch.setattr(scanned_pdf.pdfium, "PdfDocument", Mock(return_value=pdf))

    def recognize(_):
        if fail:
            raise RuntimeError("synthetic OCR failure")
        return "Dominio: AB123CD"

    document = Document("doc", "scan.pdf", "scan.pdf", "application/pdf", 3)
    extractor = scanned_pdf.ScannedPdfOcrExtractor(recognize)
    if fail:
        with pytest.raises(InvalidDocument):
            extractor.extract(document, tmp_path / "scan.pdf")
    else:
        assert "AB123CD" in extractor.extract(document, tmp_path / "scan.pdf").texto_extraido
    assert closed_pages == ([0] if fail else [0, 1])
    pdf.__exit__.assert_called_once()
    for page, bitmap in zip(pages, bitmaps, strict=True):
        page.close.assert_called_once()
        bitmap.close.assert_called_once()
