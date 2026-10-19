"""tests/unit/test_vehicle_record.py"""

from dataclasses import is_dataclass
from datetime import datetime, timezone
from unittest import TestCase
from uuid import UUID

from src.domain.vehicle_record import VehicleIntake, VehicleRecord


class TestVehicleRecord(TestCase):
    def setUp(self) -> None:
        self.datos = {
            "patente": "AB123CD",
            "marca": "Ford",
            "modelo": "Focus SE",
            "numero_motor": "MOTOR123",
            "numero_chasis": "CHASIS456",
            "anio": 2020,
        }

    def test_creacion_valida(self) -> None:
        registro = VehicleRecord(**self.datos)
        self.assertTrue(is_dataclass(registro))
        for campo, valor in self.datos.items():
            with self.subTest(campo=campo):
                self.assertEqual(getattr(registro, campo), valor)

    def test_normalizacion_de_espacios(self) -> None:
        datos = {
            campo: f" \t{valor}\n " if isinstance(valor, str) else valor
            for campo, valor in self.datos.items()
        }
        self.assertEqual(VehicleRecord(**datos), VehicleRecord(**self.datos))

    def test_mayusculas_en_identificadores(self) -> None:
        datos = self.datos.copy()
        for campo in ("patente", "numero_motor", "numero_chasis"):
            datos[campo] = f" {datos[campo].lower()} "
        self.assertEqual(VehicleRecord(**datos), VehicleRecord(**self.datos))

    def test_rechazo_de_campos_vacios(self) -> None:
        for campo in ("patente", "marca", "modelo", "numero_motor", "numero_chasis"):
            for valor in ("", "   ", "\t\n"):
                with self.subTest(campo=campo, valor=valor):
                    datos = {**self.datos, campo: valor}
                    with self.assertRaises(ValueError):
                        VehicleRecord(**datos)

    def test_rechazo_de_anio_invalido(self) -> None:
        for anio in (0, -1, -2020, None, "2020", 2020.5, True, False):
            with self.subTest(anio=anio):
                with self.assertRaises(ValueError):
                    VehicleRecord(**{**self.datos, "anio": anio})

    def test_anio_positivo_minimo(self) -> None:
        registro = VehicleRecord(**{**self.datos, "anio": 1})
        self.assertEqual(registro.anio, 1)

    def test_rechazo_de_campos_no_textuales(self) -> None:
        for campo in ("patente", "marca", "modelo", "numero_motor", "numero_chasis"):
            for valor in (None, 123):
                with self.subTest(campo=campo, valor=valor):
                    with self.assertRaises(ValueError):
                        VehicleRecord(**{**self.datos, campo: valor})


class TestVehicleIntake(TestCase):
    def setUp(self) -> None:
        self.vehicle = VehicleRecord(
            patente="AB123CD",
            marca="Ford",
            modelo="Focus SE",
            numero_motor="MOTOR123",
            numero_chasis="CHASIS456",
            anio=2020,
        )

    def test_creacion_correcta(self) -> None:
        ingreso = VehicleIntake(vehicle=self.vehicle, archivo_origen="titulo.pdf")
        self.assertTrue(is_dataclass(ingreso))
        self.assertEqual(ingreso.archivo_origen, "titulo.pdf")

    def test_id_automatico(self) -> None:
        primero = VehicleIntake(self.vehicle, "titulo.pdf")
        segundo = VehicleIntake(self.vehicle, "titulo.pdf")
        self.assertIsInstance(primero.id_interno, str)
        self.assertEqual(UUID(primero.id_interno).version, 4)
        self.assertNotEqual(primero.id_interno, segundo.id_interno)

    def test_fecha_utc(self) -> None:
        antes = datetime.now(timezone.utc)
        ingreso = VehicleIntake(self.vehicle, "titulo.pdf")
        despues = datetime.now(timezone.utc)
        self.assertIsInstance(ingreso.fecha_ingreso, datetime)
        self.assertIs(ingreso.fecha_ingreso.tzinfo, timezone.utc)
        self.assertLessEqual(antes, ingreso.fecha_ingreso)
        self.assertLessEqual(ingreso.fecha_ingreso, despues)

    def test_normalizacion_de_archivo_origen(self) -> None:
        for archivo in (
            " \ttitulo.pdf\n ",
            " /documentos/titulo.pdf ",
            " C:\\documentos\\titulo.pdf ",
            "documentos/ titulo.pdf ",
        ):
            with self.subTest(archivo=archivo):
                ingreso = VehicleIntake(self.vehicle, archivo)
                self.assertEqual(ingreso.archivo_origen, "titulo.pdf")

    def test_rechazo_de_archivo_vacio(self) -> None:
        for archivo in ("", "   ", "\t\n", "/documentos/", "C:\\documentos\\", "documentos/   "):
            with self.subTest(archivo=archivo):
                with self.assertRaises(ValueError):
                    VehicleIntake(self.vehicle, archivo)

    def test_requiere_revision_por_defecto(self) -> None:
        self.assertIs(VehicleIntake(self.vehicle, "titulo.pdf").requiere_revision, True)

    def test_asociacion_con_vehicle_record(self) -> None:
        ingreso = VehicleIntake(self.vehicle, "titulo.pdf")
        self.assertIs(ingreso.vehicle, self.vehicle)
