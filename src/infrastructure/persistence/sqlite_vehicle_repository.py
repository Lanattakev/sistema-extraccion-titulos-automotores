"""src/infrastructure/persistence/sqlite_vehicle_repository.py"""

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from src.domain.vehicle_record import VehicleIntake, VehicleRecord


class SQLiteVehicleRepository:
    """Guarda y recupera ingresos completos en una base SQLite local."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        with closing(sqlite3.connect(self._db_path)) as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS vehicle_intakes (
                        id_interno TEXT PRIMARY KEY NOT NULL,
                        fecha_ingreso TEXT NOT NULL,
                        archivo_origen TEXT NOT NULL,
                        requiere_revision INTEGER NOT NULL CHECK (requiere_revision IN (0, 1)),
                        patente TEXT NOT NULL,
                        marca TEXT NOT NULL,
                        modelo TEXT NOT NULL,
                        numero_motor TEXT NOT NULL,
                        numero_chasis TEXT NOT NULL,
                        anio INTEGER NOT NULL
                    )
                    """
                )

    def save(self, intake: VehicleIntake) -> None:
        """Inserta un ingreso; un ID repetido produce sqlite3.IntegrityError."""
        vehicle = intake.vehicle
        with closing(sqlite3.connect(self._db_path)) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO vehicle_intakes (
                        id_interno, fecha_ingreso, archivo_origen, requiere_revision,
                        patente, marca, modelo, numero_motor, numero_chasis, anio
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        intake.id_interno, intake.fecha_ingreso.isoformat(),
                        intake.archivo_origen, int(intake.requiere_revision),
                        vehicle.patente, vehicle.marca, vehicle.modelo,
                        vehicle.numero_motor, vehicle.numero_chasis, vehicle.anio,
                    ),
                )

    def get_by_id(self, id_interno: str) -> VehicleIntake | None:
        """Recupera un ingreso o devuelve None si el ID no existe."""
        with closing(sqlite3.connect(self._db_path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM vehicle_intakes WHERE id_interno = ?", (id_interno,)
            ).fetchone()
        return self._from_row(row) if row is not None else None

    def list_all(self) -> list[VehicleIntake]:
        """Lista los ingresos en orden de insercion."""
        with closing(sqlite3.connect(self._db_path)) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "SELECT * FROM vehicle_intakes ORDER BY rowid"
            ).fetchall()
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _from_row(row: sqlite3.Row) -> VehicleIntake:
        return VehicleIntake(
            vehicle=VehicleRecord(
                patente=row["patente"], marca=row["marca"], modelo=row["modelo"],
                numero_motor=row["numero_motor"], numero_chasis=row["numero_chasis"],
                anio=row["anio"],
            ),
            id_interno=row["id_interno"],
            fecha_ingreso=datetime.fromisoformat(row["fecha_ingreso"]),
            archivo_origen=row["archivo_origen"],
            requiere_revision=bool(row["requiere_revision"]),
        )
