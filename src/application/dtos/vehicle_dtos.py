"""src/application/dtos/vehicle_dtos.py - Entradas revisadas y altas vehiculares."""

from pydantic import BaseModel, ConfigDict, model_validator

from src.domain.vehicle_record import VehicleIntake, VehicleRecord


class ReviewedVehicleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    patente: str
    marca: str
    modelo: str
    numero_motor: str
    numero_chasis: str
    anio: int

    def to_vehicle(self) -> VehicleRecord:
        return VehicleRecord(**self.model_dump(exclude={"archivo_origen"}))

    @model_validator(mode="after")
    def validate_vehicle(self) -> "ReviewedVehicleRequest":
        self.to_vehicle()
        return self


class CreateVehicleRequest(ReviewedVehicleRequest):
    archivo_origen: str

    def to_intake(self) -> VehicleIntake:
        return VehicleIntake(
            vehicle=self.to_vehicle(),
            archivo_origen=self.archivo_origen,
        )

    @model_validator(mode="after")
    def validate_domain(self) -> "CreateVehicleRequest":
        self.to_intake()
        return self
