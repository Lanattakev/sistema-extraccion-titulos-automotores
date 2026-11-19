"""src/infrastructure/persistence/sqlite_history_repository.py"""

import sqlite3
from datetime import datetime
from pathlib import Path

from src.domain.history_event import HistoryEvent, HistoryEventType
from src.domain.repositories import HistoryRepository
from src.infrastructure.persistence.sqlite_connections import (
    SQLiteConnectionPool,
    sqlite_connection,
)


class SQLiteHistoryRepository(HistoryRepository):
    def __init__(self, db_path: str | Path, *, pool: SQLiteConnectionPool | None = None) -> None:
        self._db_path = str(db_path)
        self._pool = pool
        with sqlite_connection(self._db_path, self._pool) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("""
                CREATE TABLE IF NOT EXISTS history_events (
                    id_evento TEXT PRIMARY KEY NOT NULL,
                    id_documento TEXT NOT NULL REFERENCES documents(id_documento),
                    tipo_evento TEXT NOT NULL CHECK (tipo_evento IN (
                        'documento_cargado', 'documento_revisado', 'documento_registrado'
                    )),
                    fecha_evento TEXT NOT NULL,
                    nombre_original TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS history_once_per_document
                ON history_events (id_documento, tipo_evento)
                WHERE tipo_evento IN ('documento_cargado', 'documento_registrado')
            """)

    @staticmethod
    def append_in_transaction(
        connection: sqlite3.Connection,
        document_id: str,
        event_type: HistoryEventType,
        original_name: str,
    ) -> None:
        """Sin commit propio: el evento y la operacion se confirman o revierten juntos."""
        event = HistoryEvent(document_id, event_type, original_name)
        connection.execute(
            """
            INSERT INTO history_events (
                id_evento, id_documento, tipo_evento, fecha_evento, nombre_original
            ) VALUES (?, ?, ?, ?, ?)
        """,
            (
                event.id_evento,
                event.id_documento,
                event.tipo_evento,
                event.fecha_evento.isoformat(timespec="microseconds"),
                event.nombre_original,
            ),
        )

    def list_all(self) -> list[HistoryEvent]:
        with sqlite_connection(self._db_path, self._pool) as connection:
            rows = connection.execute(
                "SELECT * FROM history_events ORDER BY fecha_evento DESC, rowid DESC",
            ).fetchall()
        return [
            HistoryEvent(
                id_evento=row["id_evento"],
                id_documento=row["id_documento"],
                tipo_evento=row["tipo_evento"],
                nombre_original=row["nombre_original"],
                fecha_evento=datetime.fromisoformat(row["fecha_evento"]),
            )
            for row in rows
        ]
