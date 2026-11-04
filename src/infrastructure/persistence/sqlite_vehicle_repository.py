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
                connection.execute("BEGIN IMMEDIATE")
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
                self._migrate_registration_numbers(connection)

    @staticmethod
    def _migrate_registration_numbers(connection: sqlite3.Connection) -> None:
        """Migracion aditiva y atomica: conserva UUID, filas y relaciones existentes."""
        columns = {row[1] for row in connection.execute("PRAGMA table_info(vehicle_intakes)")}
        if "numero_registro" not in columns:
            connection.execute("""
                ALTER TABLE vehicle_intakes ADD COLUMN numero_registro INTEGER
                CHECK (numero_registro IS NULL OR
                    (typeof(numero_registro) = 'integer' AND numero_registro > 0))
            """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS vehicle_registration_sequence (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                last_value INTEGER NOT NULL CHECK (last_value >= 0)
            )
        """)
        connection.execute("""
            INSERT OR IGNORE INTO vehicle_registration_sequence VALUES (1, 0)
        """)
        connection.execute("""
            UPDATE vehicle_registration_sequence
            SET last_value = MAX(last_value,
                (SELECT COALESCE(MAX(numero_registro), 0) FROM vehicle_intakes))
            WHERE singleton = 1
        """)
        missing = connection.execute("""
            SELECT id_interno FROM vehicle_intakes
            WHERE numero_registro IS NULL ORDER BY rowid
        """).fetchall()
        for (intake_id,) in missing:
            number = SQLiteVehicleRepository._next_registration_number(connection)
            connection.execute(
                "UPDATE vehicle_intakes SET numero_registro = ? WHERE id_interno = ?",
                (number, intake_id),
            )
        connection.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS vehicle_intakes_numero_registro
            ON vehicle_intakes(numero_registro)
        """)
        # SQLite no permite agregar NOT NULL sin un valor por defecto ficticio.
        for operation in ("INSERT", "UPDATE"):
            connection.execute(f"""
                CREATE TRIGGER IF NOT EXISTS vehicle_number_required_{operation.lower()}
                BEFORE {operation} ON vehicle_intakes
                WHEN NEW.numero_registro IS NULL
                BEGIN SELECT RAISE(ABORT, 'numero_registro es obligatorio'); END
            """)

    @staticmethod
    def _next_registration_number(connection: sqlite3.Connection) -> int:
        # La escritura serializa las altas concurrentes dentro de la misma transaccion.
        connection.execute("""
            UPDATE vehicle_registration_sequence SET last_value = last_value + 1
            WHERE singleton = 1
        """)
        return connection.execute(
            "SELECT last_value FROM vehicle_registration_sequence WHERE singleton = 1"
        ).fetchone()[0]

    def save(self, intake: VehicleIntake) -> None:
        """Inserta un ingreso; un ID repetido produce sqlite3.IntegrityError."""
        with closing(sqlite3.connect(self._db_path)) as connection:
            with connection:
                self.insert_in_transaction(connection, intake)

    @staticmethod
    def insert_in_transaction(connection: sqlite3.Connection, intake: VehicleIntake) -> None:
        """Reutiliza el alta dentro de una transaccion documental sin commit propio."""
        vehicle = intake.vehicle
        number = SQLiteVehicleRepository._next_registration_number(connection)
        connection.execute(
            """
            INSERT INTO vehicle_intakes (
                id_interno, fecha_ingreso, archivo_origen, requiere_revision,
                patente, marca, modelo, numero_motor, numero_chasis, anio, numero_registro
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                intake.id_interno, intake.fecha_ingreso.isoformat(),
                intake.archivo_origen, int(intake.requiere_revision),
                vehicle.patente, vehicle.marca, vehicle.modelo,
                vehicle.numero_motor, vehicle.numero_chasis, vehicle.anio, number,
            ),
        )
        intake.numero_registro = number

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
            numero_registro=row["numero_registro"],
        )
