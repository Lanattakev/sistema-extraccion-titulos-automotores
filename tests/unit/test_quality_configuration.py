"""tests/unit/test_quality_configuration.py - OCR portable y contratos estables."""

from dataclasses import asdict, fields
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.application.document_errors import InvalidDocument
from src.application.dtos.document_dtos import BatchDocumentResult, ProposedVehicleFields
from src.domain.vehicle_record import VehicleIntake, VehicleRecord
from src.infrastructure.fastapi.document_http import document_error_status
from src.infrastructure.settings import config


@pytest.mark.parametrize(
    "platform,detected,expected",
    [
        ("win32", None, r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        ("linux", "/usr/bin/tesseract", "/usr/bin/tesseract"),
        ("linux", None, "tesseract"),
        ("darwin", "/opt/homebrew/bin/tesseract", "/opt/homebrew/bin/tesseract"),
    ],
)
def test_default_ocr_command_preserves_windows_and_detects_path(
    monkeypatch, platform, detected, expected
):
    calls = []
    monkeypatch.setattr(config, "sys", SimpleNamespace(platform=platform))

    def which(name):
        calls.append(name)
        return detected

    monkeypatch.setattr(config.shutil, "which", which)
    assert config.default_tesseract_command() == expected
    assert calls == ([] if platform == "win32" else ["tesseract"])


def test_explicit_command_environment_override_takes_precedence(monkeypatch):
    monkeypatch.setenv("TESSERACT_CMD", "/custom/tesseract")
    settings = config.Settings(_env_file=None)
    assert settings.TESSERACT_CMD == "/custom/tesseract"


def test_timeout_accepts_positive_integer_environment_value(monkeypatch):
    monkeypatch.setenv("TESSERACT_TIMEOUT", "45")
    settings = config.Settings(_env_file=None)
    assert settings.TESSERACT_TIMEOUT == 45
    assert isinstance(settings.TESSERACT_TIMEOUT, int)


@pytest.mark.parametrize("value", ["0", "-1", "0.5", "not a number"])
def test_timeout_rejects_non_positive_or_fractional_values(monkeypatch, value):
    monkeypatch.setenv("TESSERACT_TIMEOUT", value)
    with pytest.raises(ValidationError):
        config.Settings(_env_file=None)


def test_separate_batch_dto_preserves_flat_response_shape_and_failure_states():
    proposal = ProposedVehicleFields("doc", patente="AB123CD")
    result = BatchDocumentResult(**asdict(proposal), nombre_original="titulo.pdf")
    assert asdict(result) == {
        **asdict(proposal),
        "nombre_original": "titulo.pdf",
        "fallo": False,
        "error": None,
    }
    failed = BatchDocumentResult(nombre_original="bad.pdf", fallo=True, error="invalido")
    assert failed.id_documento is None
    assert failed.requiere_revision is False
    assert proposal.requiere_revision is True
    assert {item.name for item in fields(proposal)} <= {item.name for item in fields(failed)}


@pytest.mark.parametrize("year", [True, False, "2020", 0, -1, 2020.5, None])
def test_domain_still_rejects_runtime_values_outside_type_annotations(year):
    with pytest.raises(ValueError, match="anio debe ser un entero mayor que 0"):
        VehicleRecord("AB123CD", "Toyota", "Corolla", "M123", "C456", year)


@pytest.mark.parametrize("origin", [None, 12, b"titulo.pdf", " ", "path/"])
def test_source_filename_validation_is_preserved(origin):
    vehicle = VehicleRecord("AB123CD", "Toyota", "Corolla", "M123", "C456", 2020)
    with pytest.raises(ValueError):
        VehicleIntake(vehicle, origin)


def test_normalized_source_and_year_are_unchanged():
    vehicle = VehicleRecord(" ab123cd ", " Toyota ", " Corolla ", "m123", "c456", 2020)
    intake = VehicleIntake(vehicle, r" C:\folder\titulo.pdf ")
    assert vehicle.patente == "AB123CD"
    assert vehicle.anio == 2020
    assert intake.archivo_origen == "titulo.pdf"


def test_subclass_of_document_error_keeps_http_mapping():
    class DetailedInvalidDocument(InvalidDocument):
        pass

    assert document_error_status(DetailedInvalidDocument("invalido")) == 400
