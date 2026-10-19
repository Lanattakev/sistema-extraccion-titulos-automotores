"""src/domain/vehicle_record.py"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class VehicleRecord:
    """Datos normalizados y validados de un titulo vehicular."""

    patente: str
    marca: str
    modelo: str
    numero_motor: str
    numero_chasis: str
    anio: int

    def __post_init__(self) -> None:
        for campo in ("patente", "marca", "modelo", "numero_motor", "numero_chasis"):
            valor = getattr(self, campo)
            if not isinstance(valor, str):
                raise ValueError(f"{campo} debe ser texto.")
            valor = valor.strip()
            if not valor:
                raise ValueError(f"{campo} no puede quedar vacio.")
            if campo in ("patente", "numero_motor", "numero_chasis"):
                valor = valor.upper()
            setattr(self, campo, valor)

        if isinstance(self.anio, bool) or not isinstance(self.anio, int) or self.anio <= 0:
            raise ValueError("anio debe ser un entero mayor que 0.")


@dataclass
class VehicleIntake:
    """Ingreso de un vehiculo asociado a su archivo de origen."""

    vehicle: VehicleRecord
    archivo_origen: str
    id_interno: str = field(default_factory=lambda: str(uuid4()))
    fecha_ingreso: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    requiere_revision: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.archivo_origen, str):
            raise ValueError("archivo_origen debe ser texto.")
        self.archivo_origen = self.archivo_origen.strip().replace("\\", "/").rsplit("/", 1)[-1].strip()
        if not self.archivo_origen:
            raise ValueError("archivo_origen no puede quedar vacio.")
