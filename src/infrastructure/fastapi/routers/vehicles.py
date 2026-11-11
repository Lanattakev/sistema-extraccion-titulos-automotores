"""src/infrastructure/fastapi/routers/vehicles.py — Alta y consulta de vehiculos."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.application.dtos.vehicle_dtos import (
    CreateVehicleRequest as CreateVehicleRequest,
)
from src.application.dtos.vehicle_dtos import (
    ReviewedVehicleRequest as ReviewedVehicleRequest,
)
from src.application.use_cases.vehicle_intake import CreateVehicleUseCase
from src.domain.repositories import VehicleRepository
from src.domain.vehicle_record import VehicleIntake

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


def get_vehicle_repository(request: Request) -> VehicleRepository:
    return request.app.state.vehicle_repository


Repository = Annotated[VehicleRepository, Depends(get_vehicle_repository)]


def get_create_vehicle_use_case(repository: Repository) -> CreateVehicleUseCase:
    return CreateVehicleUseCase(repository)


@router.post("", response_model=VehicleIntake, status_code=status.HTTP_201_CREATED)
def create_vehicle(
    payload: CreateVehicleRequest,
    use_case: Annotated[CreateVehicleUseCase, Depends(get_create_vehicle_use_case)],
) -> VehicleIntake:
    return use_case.execute(payload)


@router.get("", response_model=list[VehicleIntake])
def list_vehicles(repository: Repository) -> list[VehicleIntake]:
    return repository.list_all()


@router.get("/{id}", response_model=VehicleIntake)
def get_vehicle(id: str, repository: Repository) -> VehicleIntake:
    intake = repository.get_by_id(id)
    if intake is None:
        raise HTTPException(status_code=404, detail="Vehiculo no encontrado")
    return intake
