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

        self.anio = validate_year(self.anio)


@dataclass
class VehicleIntake:
    """Ingreso de un vehiculo asociado a su archivo de origen."""

    vehicle: VehicleRecord
    archivo_origen: str
    id_interno: str = field(default_factory=lambda: str(uuid4()))
    fecha_ingreso: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    requiere_revision: bool = True
    numero_registro: int | None = None

    def __post_init__(self) -> None:
        self.archivo_origen = normalize_source_filename(self.archivo_origen)


def validate_year(value: object) -> int:
    """Valida entradas de Python incluso cuando no respetan las anotaciones."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("anio debe ser un entero mayor que 0.")
    return value


def normalize_source_filename(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("archivo_origen debe ser texto.")
    name = value.strip().replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not name:
        raise ValueError("archivo_origen no puede quedar vacio.")
    return name
