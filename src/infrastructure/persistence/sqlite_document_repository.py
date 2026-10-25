"""src/infrastructure/persistence/sqlite_document_repository.py"""

import sqlite3
from contextlib import closing
from dataclasses import asdict
from pathlib import Path

from src.domain.document_record import DocumentRecord
from src.domain.vehicle_record import VehicleIntake, VehicleRecord
from src.infrastructure.persistence.sqlite_history_repository import SQLiteHistoryRepository
from src.infrastructure.persistence.sqlite_vehicle_repository import SQLiteVehicleRepository


class DocumentNotFoundError(LookupError):
    """El documento no tiene un flujo persistido."""


class DocumentConflictError(ValueError):
    """El documento ya fue registrado o la revision cambio."""


class SQLiteDocumentRepository:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        with closing(self._connect()) as connection, connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id_documento TEXT PRIMARY KEY NOT NULL,
                    nombre_original TEXT NOT NULL,
                    patente TEXT, marca TEXT, modelo TEXT,
                    numero_motor TEXT, numero_chasis TEXT, anio INTEGER,
                    estado TEXT NOT NULL DEFAULT 'pendiente'
                        CHECK (estado IN ('pendiente', 'revisado', 'registrado')),
                    id_interno TEXT UNIQUE REFERENCES vehicle_intakes(id_interno),
                    CHECK ((estado = 'registrado') = (id_interno IS NOT NULL)),
                    CHECK (estado = 'pendiente' OR (
                        patente IS NOT NULL AND marca IS NOT NULL AND modelo IS NOT NULL
                        AND numero_motor IS NOT NULL AND numero_chasis IS NOT NULL
                        AND anio IS NOT NULL AND anio > 0
                    ))
                )
            """)

        self.history_repository = SQLiteHistoryRepository(db_path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def save_pending(self, document: DocumentRecord) -> None:
        """La extraccion solo actualiza pendientes; nunca pisa una revision humana."""
        fields = asdict(document)
        columns = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)
        updates = ", ".join(f"{key} = excluded.{key}" for key in fields
                            if key not in ("id_documento", "estado", "id_interno"))
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            is_new = connection.execute(
                "SELECT 1 FROM documents WHERE id_documento = ?", (document.id_documento,),
            ).fetchone() is None
            connection.execute(
                f"INSERT INTO documents ({columns}) VALUES ({placeholders}) "
                f"ON CONFLICT(id_documento) DO UPDATE SET {updates} "
                "WHERE documents.estado = 'pendiente'",
                tuple(fields.values()),
            )
            if is_new:
                self.history_repository.append_in_transaction(
                    connection, document.id_documento, "documento_cargado", document.nombre_original,
                )

    def list_all(self) -> list[DocumentRecord]:
        with closing(self._connect()) as connection:
            rows = connection.execute("SELECT * FROM documents ORDER BY rowid").fetchall()
        return [DocumentRecord(**dict(row)) for row in rows]

    @staticmethod
    def _get(connection: sqlite3.Connection, document_id: str) -> DocumentRecord:
        row = connection.execute(
            "SELECT * FROM documents WHERE id_documento = ?", (document_id,),
        ).fetchone()
        if row is None:
            raise DocumentNotFoundError("Documento no encontrado.")
        return DocumentRecord(**dict(row))

    @staticmethod
    def _write_fields(connection: sqlite3.Connection, document_id: str,
                      vehicle: VehicleRecord, state: str, intake_id: str | None = None) -> None:
        connection.execute("""
            UPDATE documents SET patente = ?, marca = ?, modelo = ?, numero_motor = ?,
                numero_chasis = ?, anio = ?, estado = ?, id_interno = ?
            WHERE id_documento = ?
        """, (*asdict(vehicle).values(), state, intake_id, document_id))

    def review(self, document_id: str, vehicle: VehicleRecord) -> DocumentRecord:
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            document = self._get(connection, document_id)
            if document.estado == "registrado":
                raise DocumentConflictError("El documento ya esta registrado.")
            self._write_fields(connection, document_id, vehicle, "revisado")
            if document.estado != "revisado" or any(
                getattr(document, key) != value for key, value in asdict(vehicle).items()
            ):
                self.history_repository.append_in_transaction(
                    connection, document_id, "documento_revisado", document.nombre_original,
                )
            return self._get(connection, document_id)

    def confirm(self, document_id: str, vehicle: VehicleRecord) -> VehicleIntake:
        with closing(self._connect()) as connection, connection:
            # El bloqueo se obtiene ANTES de leer el estado y se mantiene hasta el commit.
            connection.execute("BEGIN IMMEDIATE")
            document = self._get(connection, document_id)
            if document.estado == "registrado":
                raise DocumentConflictError("El documento ya esta registrado.")
            if document.estado == "revisado" and any(
                getattr(document, key) != value for key, value in asdict(vehicle).items()
            ):
                raise DocumentConflictError("Los campos cambiaron. Guarda la revision antes de confirmar.")
            # Compatibilidad con la confirmacion individual existente: sus seis campos
            # validados constituyen una revision explicita en la misma transaccion.
            intake = VehicleIntake(vehicle=vehicle, archivo_origen=document.nombre_original,
                                   requiere_revision=False)
            SQLiteVehicleRepository.insert_in_transaction(connection, intake)
            self._write_fields(connection, document_id, vehicle, "registrado", intake.id_interno)
            self.history_repository.append_in_transaction(
                connection, document_id, "documento_registrado", document.nombre_original,
            )
            return intake
