"""tests/unit/test_document_http_contracts.py - Adaptacion HTTP y limites de capas."""

import ast
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from starlette.datastructures import Headers, UploadFile

from src.application.document_errors import (
    DocumentTooLarge,
    InvalidDocument,
    InvalidUpload,
    UnsupportedDocument,
)
from src.application.dtos.document_dtos import (
    BatchDocumentResult,
    Document,
    DocumentUpload,
    ExtractedText,
    ProposedVehicleFields,
    RejectedDocumentUpload,
)
from src.application.dtos.vehicle_dtos import CreateVehicleRequest, ReviewedVehicleRequest
from src.application.use_cases.document_workflow import ConfirmDocumentUseCase
from src.domain.repositories import DocumentConflictError, DocumentNotFoundError
from src.infrastructure import extracted_text
from src.infrastructure.fastapi.document_dependencies import get_confirm_use_case
from src.infrastructure.fastapi.document_http import (
    DocumentRoute,
    to_batch_upload,
    to_document_upload,
)
from src.infrastructure.fastapi.routers import documents, vehicles
from src.infrastructure.persistence import local_document_storage


@pytest.mark.parametrize(
    "error,expected_status",
    [
        (InvalidDocument("invalido"), 400),
        (DocumentNotFoundError("ausente"), 404),
        (DocumentConflictError("conflicto"), 409),
        (DocumentTooLarge("grande"), 413),
        (UnsupportedDocument("formato"), 415),
        (InvalidUpload("sin archivo"), 422),
    ],
)
def test_application_errors_keep_http_status_and_detail(error, expected_status):
    router = APIRouter(route_class=DocumentRoute)

    @router.get("/fail")
    def fail():
        raise error

    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get("/fail")
    assert response.status_code == expected_status
    assert response.json() == {"detail": str(error)}


def test_unexpected_endpoint_error_is_not_disguised_as_validation_error():
    router = APIRouter(route_class=DocumentRoute)

    @router.get("/fail")
    def fail():
        raise RuntimeError("unexpected")

    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client, pytest.raises(RuntimeError, match="unexpected"):
        client.get("/fail")


def test_confirm_endpoint_supports_use_case_dependency_override():
    case = Mock(spec=ConfirmDocumentUseCase)
    case.execute.side_effect = DocumentConflictError("revision cambiada")
    app = FastAPI()
    app.include_router(documents.router)
    app.dependency_overrides[get_confirm_use_case] = lambda: case
    payload = {
        "patente": "AB123CD",
        "marca": "Toyota",
        "modelo": "Corolla",
        "numero_motor": "M123",
        "numero_chasis": "C456",
        "anio": 2020,
    }
    with TestClient(app) as client:
        response = client.post("/documents/doc/confirm", json=payload)
    assert response.status_code == 409
    args = case.execute.call_args.args
    assert args[0] == "doc"
    assert isinstance(args[1], ReviewedVehicleRequest)


@pytest.mark.parametrize(
    "disposition",
    [
        'form-data; name="file"; filename="C:/titulo.pdf"',
        'form-data; name="file"; filename="folder\\titulo.pdf"',
    ],
)
def test_multipart_path_validation_precedes_storage(disposition):
    file = UploadFile(
        filename="titulo.pdf",
        file=BytesIO(b"synthetic"),
        headers=Headers({"content-disposition": disposition}),
    )
    with pytest.raises(InvalidDocument, match="El nombre no puede contener rutas."):
        to_document_upload(file)
    rejected = to_batch_upload(file)
    assert isinstance(rejected, RejectedDocumentUpload)
    assert rejected.nombre_original == "titulo.pdf"


def test_multipart_adapter_keeps_binary_stream_and_rejects_text_fields():
    source = BytesIO(b"synthetic")
    upload = to_document_upload(UploadFile(filename="titulo.pdf", file=source))
    assert isinstance(upload, DocumentUpload)
    assert upload.source is source
    assert upload.nombre_original == "titulo.pdf"
    with pytest.raises(InvalidUpload):
        to_document_upload("text field")
    assert isinstance(to_batch_upload("text field"), RejectedDocumentUpload)


def test_dtos_are_defined_in_application_and_legacy_imports_keep_identity():
    from src.application import title_field_extraction

    for dto in [
        BatchDocumentResult,
        Document,
        ExtractedText,
        ProposedVehicleFields,
        CreateVehicleRequest,
        ReviewedVehicleRequest,
    ]:
        assert dto.__module__.startswith("src.application.dtos.")
    assert documents.BatchDocumentResult is BatchDocumentResult
    assert vehicles.ReviewedVehicleRequest is ReviewedVehicleRequest
    assert vehicles.CreateVehicleRequest is CreateVehicleRequest
    assert local_document_storage.Document is Document
    assert local_document_storage.InvalidDocument is InvalidDocument
    assert local_document_storage.DocumentTooLarge is DocumentTooLarge
    assert extracted_text.ExtractedText is ExtractedText
    assert title_field_extraction.ProposedVehicleFields is ProposedVehicleFields


def test_router_endpoints_remain_short_and_do_not_orchestrate_processing():
    directory = Path(__file__).resolve().parents[2] / "src/infrastructure/fastapi/routers"
    forbidden_calls = {
        "save_document",
        "extract_title_fields",
        "extract_pdf_text",
        "extract_image_text",
        "save_pending",
        "review",
        "confirm",
        "to_intake",
    }
    endpoints = []
    for path in directory.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if (
                not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                or not node.decorator_list
            ):
                continue
            endpoints.append(node.name)
            assert node.end_lineno - node.lineno + 1 <= 20, (path, node.name)
            assert not any(
                isinstance(child, (ast.For, ast.AsyncFor, ast.While)) for child in ast.walk(node)
            )
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    name = (
                        child.func.attr
                        if isinstance(child.func, ast.Attribute)
                        else getattr(child.func, "id", "")
                    )
                    assert name not in forbidden_calls, (path, node.name, name)
    assert "create_document_batch" in endpoints
    assert "confirm_document" in endpoints
