"""tests/integration/test_sqlite_vehicle_repository.py"""

import sqlite3
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
