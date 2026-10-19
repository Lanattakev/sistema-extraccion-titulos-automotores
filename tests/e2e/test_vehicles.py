"""tests/e2e/test_vehicles.py — Contrato HTTP y persistencia de vehiculos."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.infrastructure.settings.config import get_settings
from src.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(get_settings(), "DATABASE_URL", f"sqlite:///{tmp_path / 'vehicles.db'}")
    with TestClient(create_app()) as client:
        yield client


def payload() -> dict[str, str | int]:
    return {
        "patente": " ab123cd ", "marca": "Toyota", "modelo": "Corolla",
        "numero_motor": "motor1", "numero_chasis": "chasis1", "anio": 2020,
        "archivo_origen": "titulos/auto.pdf",
    }


def test_create_list_and_get_vehicle(client: TestClient) -> None:
    assert client.get("/api/v1/vehicles").json() == []
    response = client.post("/api/v1/vehicles", json=payload())
    assert response.status_code == 201
    intake = response.json()
    assert intake["vehicle"]["patente"] == "AB123CD"
    assert intake["archivo_origen"] == "auto.pdf"
    assert intake["requiere_revision"] is True
    assert intake["fecha_ingreso"]
    detail = client.get(f"/api/v1/vehicles/{intake['id_interno']}")
    assert detail.status_code == 200
    assert detail.json() == intake
    assert client.get("/api/v1/vehicles").json() == [intake]


def test_missing_vehicle(client: TestClient) -> None:
    assert client.get("/api/v1/vehicles/missing").status_code == 404


@pytest.mark.parametrize("field,value", [
    ("patente", " "), ("archivo_origen", " "), ("anio", 0),
    ("anio", True), ("anio", "2020"), ("marca", None),
])
def test_invalid_vehicle(client: TestClient, field: str, value: object) -> None:
    body = dict(payload())
    body[field] = value
    assert client.post("/api/v1/vehicles", json=body).status_code == 422
    assert client.get("/api/v1/vehicles").json() == []
