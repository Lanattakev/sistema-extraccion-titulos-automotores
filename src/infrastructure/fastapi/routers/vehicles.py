"""src/infrastructure/fastapi/routers/vehicles.py — Alta y consulta de vehiculos."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, model_validator

from src.domain.vehicle_record import VehicleIntake, VehicleRecord
from src.infrastructure.persistence.sqlite_vehicle_repository import SQLiteVehicleRepository

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


def get_vehicle_repository(request: Request) -> SQLiteVehicleRepository:
    return request.app.state.vehicle_repository


Repository = Annotated[SQLiteVehicleRepository, Depends(get_vehicle_repository)]


class CreateVehicleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    patente: str
    marca: str
    modelo: str
    numero_motor: str
    numero_chasis: str
    anio: int
    archivo_origen: str

    def to_intake(self) -> VehicleIntake:
        return VehicleIntake(
            vehicle=VehicleRecord(**self.model_dump(exclude={"archivo_origen"})),
            archivo_origen=self.archivo_origen,
        )

    @model_validator(mode="after")
    def validate_domain(self) -> "CreateVehicleRequest":
        self.to_intake()
        return self


@router.post("", response_model=VehicleIntake, status_code=status.HTTP_201_CREATED)
def create_vehicle(payload: CreateVehicleRequest, repository: Repository) -> VehicleIntake:
    intake = payload.to_intake()
    repository.save(intake)
    return intake


@router.get("", response_model=list[VehicleIntake])
def list_vehicles(repository: Repository) -> list[VehicleIntake]:
    return repository.list_all()


@router.get("/{id}", response_model=VehicleIntake)
def get_vehicle(id: str, repository: Repository) -> VehicleIntake:
    intake = repository.get_by_id(id)
    if intake is None:
        raise HTTPException(status_code=404, detail="Vehiculo no encontrado")
    return intake
