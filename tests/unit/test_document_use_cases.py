"""tests/unit/test_document_use_cases.py - Casos de uso sin disco, SQLite ni OCR."""

import asyncio
import subprocess
import sys
from io import BytesIO
from threading import Event, get_ident
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from src.application.document_errors import DocumentTooLarge, InvalidDocument, InvalidUpload
from src.application.dtos.document_dtos import (
    Document,
    DocumentUpload,
    ExtractedText,
    ProposedVehicleFields,
    RejectedDocumentUpload,
)
from src.application.dtos.vehicle_dtos import CreateVehicleRequest, ReviewedVehicleRequest
from src.application.use_cases.document_extraction import (
    ExtractDocumentFieldsUseCase,
    ExtractDocumentTextUseCase,
)
from src.application.use_cases.document_workflow import (
    ConfirmDocumentUseCase,
    ReviewDocumentUseCase,
    UploadDocumentUseCase,
)
from src.application.use_cases.process_batch_documents import ProcessBatchDocumentsUseCase
from src.application.use_cases.vehicle_intake import CreateVehicleUseCase
from src.domain.document_record import DocumentRecord
from src.domain.repositories import DocumentConflictError, DocumentNotFoundError, DocumentRepository
from src.domain.vehicle_record import VehicleIntake

FIELDS = {
    "patente": " ab123cd ",
    "marca": "Toyota",
    "modelo": "Corolla",
    "numero_motor": "m123",
    "numero_chasis": "c456",
    "anio": 2020,
}


def test_use_cases_import_without_frameworks_or_infrastructure():
    code = """
import sys
from src.application.use_cases import document_extraction, document_workflow
from src.application.use_cases import process_batch_documents, vehicle_intake
for name in sys.modules:
    assert not name.startswith(('fastapi', 'starlette', 'src.infrastructure', 'pypdf', 'pytesseract'))
"""
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", code], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_text_extraction_uses_injected_operations():
    document = Document("doc", "titulo.pdf", "doc.pdf", "application/pdf", 20)
    extracted = ExtractedText("doc", "titulo.pdf", "Dominio: AB123CD", 16, False, "ok")
    load, read = Mock(return_value=document), Mock(return_value=extracted)
    assert ExtractDocumentTextUseCase(load, read).execute("doc") is extracted
    load.assert_called_once_with("doc")
    read.assert_called_once_with(document)


def test_missing_document_becomes_domain_error_without_running_extraction():
    read = Mock()
    case = ExtractDocumentTextUseCase(Mock(side_effect=FileNotFoundError), read)
    with pytest.raises(DocumentNotFoundError, match="Documento no encontrado."):
        case.execute("missing")
    read.assert_not_called()


def test_field_extraction_preserves_partial_proposals_without_creating_intakes():
    repository = Mock(spec=DocumentRepository)
    text = ExtractedText("doc", "titulo.pdf", "Dominio: AB123CD", 16, False, "ok")
    proposal = ExtractDocumentFieldsUseCase(Mock(return_value=text), repository).execute("doc")
    assert proposal.requiere_revision is True
    assert proposal.patente == "AB123CD"
    assert proposal.marca is None
    repository.save_pending.assert_called_once_with(
        DocumentRecord("doc", "titulo.pdf", patente="AB123CD")
    )
    repository.confirm.assert_not_called()
    repository.review.assert_not_called()


def test_extraction_failure_does_not_save_a_pending_document():
    repository = Mock(spec=DocumentRepository)
    case = ExtractDocumentFieldsUseCase(Mock(side_effect=InvalidDocument("ilegible")), repository)
    with pytest.raises(InvalidDocument, match="ilegible"):
        case.execute("doc")
    repository.save_pending.assert_not_called()


def test_upload_stores_file_before_saving_pending_metadata():
    calls = []
    upload = DocumentUpload(BytesIO(b"synthetic"), "titulo.pdf")
    document = Document("doc", "titulo.pdf", "doc.pdf", "application/pdf", 9)

    def save(source, name):
        calls.append((source.read(), name))
        return document

    repository = Mock(spec=DocumentRepository)
    repository.save_pending.side_effect = lambda record: calls.append(record)
    assert UploadDocumentUseCase(save, repository).execute(upload) is document
    assert calls == [(b"synthetic", "titulo.pdf"), DocumentRecord("doc", "titulo.pdf")]


def test_failed_upload_never_writes_pending_metadata():
    repository = Mock(spec=DocumentRepository)
    case = UploadDocumentUseCase(Mock(side_effect=DocumentTooLarge("grande")), repository)
    with pytest.raises(DocumentTooLarge):
        case.execute(DocumentUpload(BytesIO(), "titulo.pdf"))
    repository.save_pending.assert_not_called()


@pytest.mark.parametrize(
    "operation,case_type",
    [
        ("confirm", ConfirmDocumentUseCase),
        ("review", ReviewDocumentUseCase),
    ],
)
def test_review_and_confirmation_delegate_normalized_data(operation, case_type):
    repository = Mock(spec=DocumentRepository)
    payload = ReviewedVehicleRequest(**FIELDS)
    expected = getattr(repository, operation).return_value
    assert case_type(repository).execute("doc", payload) is expected
    getattr(repository, operation).assert_called_once_with("doc", payload.to_vehicle())
    repository.save_pending.assert_not_called()


@pytest.mark.parametrize(
    "error", [DocumentNotFoundError("missing"), DocumentConflictError("conflict")]
)
def test_confirmation_preserves_domain_errors(error):
    repository = Mock(spec=DocumentRepository)
    repository.confirm.side_effect = error
    with pytest.raises(type(error)) as raised:
        ConfirmDocumentUseCase(repository).execute("doc", ReviewedVehicleRequest(**FIELDS))
    assert raised.value is error


def test_independent_intake_still_requires_review_and_normalizes_origin():
    repository = Mock()
    payload = CreateVehicleRequest(**FIELDS, archivo_origen="folder/titulo.pdf")
    intake = CreateVehicleUseCase(repository).execute(payload)
    assert intake.requiere_revision is True
    assert intake.archivo_origen == "titulo.pdf"
    assert intake.vehicle.patente == "AB123CD"
    repository.save.assert_called_once_with(intake)


@pytest.mark.parametrize(
    "field,value",
    [
        ("patente", " "),
        ("anio", True),
        ("anio", "2020"),
        ("anio", 0),
        ("marca", None),
        ("extra", "not allowed"),
    ],
)
def test_moved_request_dtos_keep_strict_validation(field, value):
    with pytest.raises(ValidationError):
        ReviewedVehicleRequest(**{**FIELDS, field: value})


def test_batch_keeps_order_continues_after_errors_and_preserves_stored_ids():
    calls = []

    def save(source, name):
        calls.append(name)
        if name == "large.pdf":
            raise DocumentTooLarge("demasiado grande")
        return Document(name, name, name, "application/pdf", 10)

    def extract(identifier):
        if identifier == "broken.pdf":
            raise InvalidDocument("PDF invalido")
        if identifier == "unexpected.pdf":
            raise RuntimeError("internal secret detail")
        return ProposedVehicleFields(identifier, patente="AB123CD")

    names = ["one.pdf", "large.pdf", "broken.pdf", "unexpected.pdf", "last.pdf"]
    results = asyncio.run(
        ProcessBatchDocumentsUseCase(save, extract).execute(
            [DocumentUpload(BytesIO(b"pdf"), name) for name in names]
        )
    )
    assert calls == names
    assert [item.nombre_original for item in results] == names
    assert [item.fallo for item in results] == [False, True, True, True, False]
    assert [item.id_documento for item in results] == [
        "one.pdf",
        None,
        "broken.pdf",
        "unexpected.pdf",
        "last.pdf",
    ]
    assert results[1].error == "demasiado grande"
    assert results[2].error == "PDF invalido"
    assert results[3].error == "No se pudo procesar el documento por un error interno."
    for item in results[1:4]:
        assert item.requiere_revision is False
        assert item.patente is None
    assert results[-1].requiere_revision is True


def test_batch_rejected_uploads_do_not_reach_storage():
    save = Mock()
    case = ProcessBatchDocumentsUseCase(save, Mock())
    results = asyncio.run(
        case.execute([RejectedDocumentUpload("", InvalidUpload("El archivo debe tener nombre."))])
    )
    assert results[0].fallo is True
    assert results[0].id_documento is None
    assert results[0].error == "El archivo debe tener nombre."
    save.assert_not_called()
    assert asyncio.run(case.execute([])) == []


def test_batch_does_not_block_event_loop():
    gate = Event()
    main_thread = get_ident()
    worker_threads = []

    def save(source, name):
        worker_threads.append(get_ident())
        assert gate.wait(timeout=2), "El event loop quedo bloqueado"
        return Document("doc", name, "doc.pdf", "application/pdf", 10)

    async def heartbeat():
        await asyncio.sleep(0)
        gate.set()

    async def run():
        case = ProcessBatchDocumentsUseCase(
            save, lambda identifier: ProposedVehicleFields(identifier)
        )
        results, _ = await asyncio.gather(
            case.execute([DocumentUpload(BytesIO(b"pdf"), "titulo.pdf")]), heartbeat()
        )
        return results

    results = asyncio.run(run())
    assert not results[0].fallo
    assert worker_threads and all(thread != main_thread for thread in worker_threads)


def test_confirmation_returns_repository_intake_without_rebuilding_it():
    payload = ReviewedVehicleRequest(**FIELDS)
    intake = VehicleIntake(payload.to_vehicle(), "titulo.pdf", requiere_revision=False)
    repository = Mock(spec=DocumentRepository)
    repository.confirm.return_value = intake
    assert ConfirmDocumentUseCase(repository).execute("doc", payload) is intake
