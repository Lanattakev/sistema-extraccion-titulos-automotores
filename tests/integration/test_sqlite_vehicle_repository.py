"""tests/integration/test_sqlite_vehicle_repository.py"""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import asdict
from datetime import timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from src.domain.vehicle_record import VehicleIntake, VehicleRecord
from src.infrastructure.persistence.sqlite_vehicle_repository import SQLiteVehicleRepository


class TestSQLiteVehicleRepository(TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory(dir=".")
        self.addCleanup(self.directory.cleanup)
        self.db_path = Path(self.directory.name) / "vehicles.sqlite3"
        self.repository = SQLiteVehicleRepository(self.db_path)
        self.intake = VehicleIntake(
            vehicle=VehicleRecord(
                patente="AB123CD", marca="Ford", modelo="Focus SE",
                numero_motor="MOTOR123", numero_chasis="CHASIS456", anio=2020,
            ),
            archivo_origen="titulo.pdf",
        )

    def test_creacion_automatica_y_lista_vacia(self) -> None:
        self.assertTrue(self.db_path.is_file())
        self.assertEqual(self.repository.list_all(), [])

    def test_guardar_y_recuperar_ingreso_completo(self) -> None:
        self.repository.save(self.intake)
        recovered = self.repository.get_by_id(self.intake.id_interno)
        self.assertEqual(recovered, self.intake)
        self.assertIsInstance(recovered, VehicleIntake)
        self.assertIsInstance(recovered.vehicle, VehicleRecord)
        self.assertEqual(recovered.fecha_ingreso.tzinfo, timezone.utc)
        self.assertIs(recovered.requiere_revision, True)

    def test_id_inexistente(self) -> None:
        self.assertIsNone(self.repository.get_by_id("inexistente"))

    def test_persistencia_al_reabrir_y_tabla_existente(self) -> None:
        self.repository.save(self.intake)
        reopened = SQLiteVehicleRepository(str(self.db_path))
        self.assertEqual(reopened.get_by_id(self.intake.id_interno), self.intake)

    def test_listar_todos_y_preservar_revision_false(self) -> None:
        second = VehicleIntake(self.intake.vehicle, "segundo.pdf", requiere_revision=False)
        self.repository.save(self.intake)
        self.repository.save(second)
        recovered = self.repository.list_all()
        self.assertEqual(recovered, [self.intake, second])
        self.assertIs(recovered[1].requiere_revision, False)

    def test_id_duplicado_no_sobrescribe(self) -> None:
        self.repository.save(self.intake)
        duplicate = VehicleIntake(
            self.intake.vehicle, "otro.pdf", id_interno=self.intake.id_interno
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.repository.save(duplicate)
        self.assertEqual(self.repository.list_all(), [self.intake])

    def test_consulta_parametrizada(self) -> None:
        self.intake.archivo_origen = "titulo 'especial'.pdf"
        self.repository.save(self.intake)
        self.assertIsNone(self.repository.get_by_id("' OR 1=1 --"))
        self.assertEqual(self.repository.get_by_id(self.intake.id_interno), self.intake)

    def test_secuencia_persistente_y_rollback_sin_consumir_numero(self) -> None:
        self.intake.numero_registro = 900  # El numero siempre lo asigna el repositorio.
        self.repository.save(self.intake)
        self.assertEqual(self.intake.numero_registro, 1)
        with self.assertRaises(sqlite3.IntegrityError):
            self.repository.save(self.intake)
        reopened = SQLiteVehicleRepository(self.db_path)
        second = VehicleIntake(self.intake.vehicle, "segundo.pdf")
        reopened.save(second)
        self.assertEqual(second.numero_registro, 2)

    def test_altas_concurrentes_reciben_numeros_unicos(self) -> None:
        def save(index):
            intake = VehicleIntake(self.intake.vehicle, f"titulo-{index}.pdf")
            self.repository.save(intake)
            return intake.numero_registro

        with ThreadPoolExecutor(max_workers=4) as pool:
            numbers = list(pool.map(save, range(12)))
        self.assertEqual(sorted(numbers), list(range(1, 13)))

    def test_sqlite_rechaza_numero_duplicado_invalido_o_nulo(self) -> None:
        self.repository.save(self.intake)
        second = VehicleIntake(self.intake.vehicle, "segundo.pdf")
        self.repository.save(second)
        for value in (1, None, 0, -1, 1.5, "invalido"):
            with self.subTest(value=value):
                with closing(sqlite3.connect(self.db_path)) as connection, connection:
                    with self.assertRaises(sqlite3.IntegrityError):
                        connection.execute(
                            "UPDATE vehicle_intakes SET numero_registro = ? WHERE id_interno = ?",
                            (value, second.id_interno),
                        )

    def test_migracion_preserva_datos_orden_uuid_y_relaciones(self) -> None:
        legacy_path = Path(self.directory.name) / "legacy.sqlite3"
        original = [self.intake, VehicleIntake(self.intake.vehicle, "segundo.pdf")]
        with closing(sqlite3.connect(legacy_path)) as connection, connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("""
                CREATE TABLE vehicle_intakes (
                    id_interno TEXT PRIMARY KEY NOT NULL, fecha_ingreso TEXT NOT NULL,
                    archivo_origen TEXT NOT NULL, requiere_revision INTEGER NOT NULL,
                    patente TEXT NOT NULL, marca TEXT NOT NULL, modelo TEXT NOT NULL,
                    numero_motor TEXT NOT NULL, numero_chasis TEXT NOT NULL, anio INTEGER NOT NULL
                )
            """)
            connection.execute("""
                CREATE TABLE legacy_links (
                    vehicle_id TEXT REFERENCES vehicle_intakes(id_interno)
                )
            """)
            for intake in original:
                connection.execute(
                    "INSERT INTO vehicle_intakes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (intake.id_interno, intake.fecha_ingreso.isoformat(), intake.archivo_origen,
                     int(intake.requiere_revision), *asdict(intake.vehicle).values()),
                )
                connection.execute("INSERT INTO legacy_links VALUES (?)", (intake.id_interno,))
        migrated = SQLiteVehicleRepository(legacy_path)
        for number, (before, after) in enumerate(zip(original, migrated.list_all(), strict=True), 1):
            self.assertEqual(after.numero_registro, number)
            self.assertEqual(asdict(after), {**asdict(before), "numero_registro": number})
        reopened = SQLiteVehicleRepository(legacy_path)
        self.assertEqual(reopened.list_all(), migrated.list_all())
        third = VehicleIntake(self.intake.vehicle, "tercero.pdf")
        reopened.save(third)
        self.assertEqual(third.numero_registro, 3)
        with closing(sqlite3.connect(legacy_path)) as connection:
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(connection.execute("SELECT * FROM legacy_links").fetchall(),
                             [(intake.id_interno,) for intake in original])
