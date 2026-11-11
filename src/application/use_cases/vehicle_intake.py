"""src/application/use_cases/vehicle_intake.py - Alta independiente de vehiculos."""

from src.application.dtos.vehicle_dtos import CreateVehicleRequest
from src.domain.repositories import VehicleRepository
from src.domain.vehicle_record import VehicleIntake


class CreateVehicleUseCase:
    def __init__(self, repository: VehicleRepository) -> None:
        self.repository = repository

    def execute(self, payload: CreateVehicleRequest) -> VehicleIntake:
        intake = payload.to_intake()
        self.repository.save(intake)
        return intake
