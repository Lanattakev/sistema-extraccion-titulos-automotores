"""tests/integration/test_sqlite_concurrency.py"""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, closing
from threading import Barrier, Event

import pytest
from fastapi.testclient import TestClient

from src.domain.document_record import DocumentRecord
from src.domain.vehicle_record import VehicleRecord
from src.infrastructure.persistence import sqlite_connections
from src.infrastructure.persistence.sqlite_connections import (
    SQLiteConnectionPool,
    sqlite_connection,
)
from src.infrastructure.persistence.sqlite_document_repository import SQLiteDocumentRepository
from src.infrastructure.persistence.sqlite_vehicle_repository import SQLiteVehicleRepository
from src.infrastructure.settings.config import Settings, get_settings
from src.main import create_app


def test_every_connection_has_required_pragmas_and_is_reused(tmp_path):
    with closing(SQLiteConnectionPool(tmp_path / "pragmas.db", 3)) as pool:
        with ExitStack() as stack:
            connections = [stack.enter_context(pool.connection()) for _ in range(3)]
            assert len({id(connection) for connection in connections}) == 3
            for connection in connections:
                for pragma, expected in (
                    ("journal_mode", "wal"),
                    ("synchronous", 1),
                    ("busy_timeout", 30000),
                    ("foreign_keys", 1),
                ):
                    assert connection.execute(f"PRAGMA {pragma}").fetchone()[0] == expected
        with pool.connection() as reused:
            assert reused in connections
    for connection in connections:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")


@pytest.mark.parametrize("version", [(3, 49, 1), (3, 50, 6), (3, 51, 2), (3, 44, 5)])
def test_unsafe_runtime_rejected_before_creating_database(tmp_path, monkeypatch, version):
    monkeypatch.setattr(sqlite3, "sqlite_version_info", version)
    path = tmp_path / "untouched.db"
    with pytest.raises(RuntimeError, match="WAL concurrente"):
        SQLiteConnectionPool(path)
    assert not path.exists()


@pytest.mark.parametrize("version", [(3, 44, 6), (3, 50, 7), (3, 51, 3), (3, 54, 1)])
def test_fixed_runtime_versions_accepted(monkeypatch, version):
    monkeypatch.setattr(sqlite3, "sqlite_version_info", version)
    sqlite_connections.require_safe_sqlite()


def test_pool_exhaustion_release_and_shutdown(tmp_path):
    pool = SQLiteConnectionPool(tmp_path / "lifecycle.db", 1, acquire_timeout=0.1)
    with pool.connection() as connection:
        with ThreadPoolExecutor(max_workers=1) as executor:

            def borrow():
                with pool.connection() as borrowed:
                    return borrowed.execute("SELECT 1").fetchone()[0]

            future = executor.submit(borrow)
            with pytest.raises(TimeoutError):
                future.result(timeout=5)
        pool.close()
        # El cierre no interrumpe a quien ya posee una conexion.
        assert connection.execute("SELECT 1").fetchone()[0] == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connection.execute("SELECT 1")
    with pytest.raises(RuntimeError, match="cerrado"):
        with pool.connection():
            pytest.fail("No se debe prestar despues del cierre")
    pool.close()


def test_waiting_borrower_receives_released_connection(tmp_path):
    with closing(SQLiteConnectionPool(tmp_path / "waiting.db", 1)) as pool:
        started = Event()
        with ThreadPoolExecutor(max_workers=1) as executor:
            with pool.connection() as connection:

                def borrow():
                    started.set()
                    with pool.connection() as borrowed:
                        return borrowed is connection

                future = executor.submit(borrow)
                assert started.wait(5)
            assert future.result(timeout=5)


def test_shutdown_wakes_waiting_borrower(tmp_path):
    pool = SQLiteConnectionPool(tmp_path / "shutdown.db", 1)
    started = Event()
    with pool.connection():
        with ThreadPoolExecutor(max_workers=1) as executor:

            def borrow():
                started.set()
                with pool.connection():
                    pytest.fail("Un pool cerrado no entrega conexiones")

            future = executor.submit(borrow)
            assert started.wait(5)
            pool.close()
            with pytest.raises(RuntimeError, match="cerrado"):
                future.result(timeout=5)


def test_partial_initialization_closes_previous_connections(tmp_path, monkeypatch):
    original = sqlite_connections._open_connection
    opened = []

    def failing_open(path):
        if opened:
            raise sqlite3.OperationalError("simulated configuration failure")
        connection = original(path)
        opened.append(connection)
        return connection

    monkeypatch.setattr(sqlite_connections, "_open_connection", failing_open)
    with pytest.raises(sqlite3.OperationalError, match="simulated"):
        SQLiteConnectionPool(tmp_path / "partial.db", 2)
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        opened[0].execute("SELECT 1")


def test_rollback_foreign_keys_and_connection_reuse(tmp_path):
    with closing(SQLiteConnectionPool(tmp_path / "rollback.db", 1)) as pool:
        with pool.connection() as connection:
            connection.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
            connection.execute("CREATE TABLE child (parent_id INTEGER REFERENCES parent(id))")
        with pytest.raises(sqlite3.IntegrityError):
            with pool.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("INSERT INTO parent VALUES (1)")
                connection.execute("INSERT INTO child VALUES (2)")
        with pool.connection() as connection:
            assert not connection.in_transaction
            assert connection.execute("SELECT * FROM parent").fetchall() == []
            connection.execute("INSERT INTO parent VALUES (3)")
        with pool.connection() as connection:
            assert connection.execute("SELECT id FROM parent").fetchone()[0] == 3


def test_wal_reader_snapshot_does_not_block_writer(tmp_path):
    with closing(SQLiteConnectionPool(tmp_path / "snapshots.db", 3)) as pool:
        with pool.connection() as connection:
            connection.execute("CREATE TABLE snapshot (value INTEGER)")
            connection.execute("INSERT INTO snapshot VALUES (0)")
        with pool.connection() as reader:
            reader.execute("BEGIN")
            assert reader.execute("SELECT value FROM snapshot").fetchone()[0] == 0
            with pool.connection() as writer:
                writer.execute("BEGIN IMMEDIATE")
                writer.execute("UPDATE snapshot SET value = 1")
                with pool.connection() as observer:
                    assert observer.execute("SELECT value FROM snapshot").fetchone()[0] == 0
            # El escritor ya confirmo aun cuando el lector conserva su snapshot.
            assert reader.execute("SELECT value FROM snapshot").fetchone()[0] == 0
            with pool.connection() as observer:
                assert observer.execute("SELECT value FROM snapshot").fetchone()[0] == 1


def test_parallel_readers_and_confirmations_preserve_atomicity(tmp_path):
    path = tmp_path / "concurrent.db"
    vehicle = VehicleRecord("AB123CD", "Toyota", "Corolla", "M123", "C456", 2020)
    count = 40
    with closing(SQLiteConnectionPool(path, 4)) as pool:
        vehicles = SQLiteVehicleRepository(path, pool=pool)
        documents = SQLiteDocumentRepository(path, pool=pool)
        for index in range(count):
            documents.save_pending(DocumentRecord(f"doc-{index}", f"titulo-{index}.pdf"))
            documents.review(f"doc-{index}", vehicle)
        barrier = Barrier(8)

        def write(offset):
            barrier.wait(timeout=10)
            for index in range(offset, count, 2):
                documents.confirm(f"doc-{index}", vehicle)

        def read(_):
            barrier.wait(timeout=10)
            for _ in range(50):
                assert len(documents.list_all()) == count
                vehicles.list_all()
                documents.history_repository.list_all()
                # Cada SELECT usa el mismo snapshot para documento/alta/historial.
                with pool.connection() as connection:
                    assert (
                        connection.execute("""
                        SELECT count(*) FROM documents d
                        LEFT JOIN vehicle_intakes v ON v.id_interno = d.id_interno
                        WHERE d.estado = 'registrado' AND
                          (v.id_interno IS NULL OR NOT EXISTS (
                            SELECT 1 FROM history_events h WHERE h.id_documento = d.id_documento
                            AND h.tipo_evento = 'documento_registrado'))
                    """).fetchone()[0]
                        == 0
                    )

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(write, offset) for offset in range(2)]
            futures += [executor.submit(read, index) for index in range(6)]
            for future in futures:
                future.result(timeout=60)
        assert sorted(item.numero_registro for item in vehicles.list_all()) == list(
            range(1, count + 1)
        )
        assert all(item.estado == "registrado" for item in documents.list_all())
        assert len(documents.history_repository.list_all()) == count * 3
        with pool.connection() as connection:
            assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_pool_path_and_configuration_validation(tmp_path):
    with pytest.raises(ValueError, match="positivos"):
        SQLiteConnectionPool(tmp_path / "invalid.db", 0)
    with pytest.raises(ValueError, match="positivos"):
        SQLiteConnectionPool(tmp_path / "invalid.db", acquire_timeout=0)
    with pytest.raises(ValueError):
        Settings(SQLITE_POOL_SIZE=0)
    with closing(SQLiteConnectionPool(tmp_path / "one.db")) as pool:
        with pytest.raises(ValueError, match="otra base"):
            with sqlite_connection(tmp_path / "two.db", pool):
                pytest.fail("No debe utilizar otra base")
    with pytest.raises(ValueError, match="admitir WAL"):
        with sqlite_connection(":memory:"):
            pytest.fail("No hay WAL para una base en memoria")


def test_lifespan_shares_pool_closes_it_and_preserves_database(tmp_path, monkeypatch):
    path = tmp_path / "application.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path.as_posix()}")
    monkeypatch.setenv("SQLITE_POOL_SIZE", "2")
    get_settings.cache_clear()
    try:
        app = create_app()
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
            pool = app.state.sqlite_connections
            assert app.state.vehicle_repository._pool is pool
            assert app.state.document_repository._pool is pool
            assert app.state.history_repository._pool is pool
            app.state.document_repository.save_pending(DocumentRecord("retained", "titulo.pdf"))
        with pytest.raises(RuntimeError, match="cerrado"):
            with pool.connection():
                pytest.fail("El lifespan debe cerrar el pool")
        with TestClient(create_app()) as reopened:
            assert reopened.app.state.document_repository.list_all()[0].id_documento == "retained"
    finally:
        get_settings.cache_clear()


def test_startup_failure_closes_pool(tmp_path, monkeypatch):
    import src.main as main

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'startup.db').as_posix()}")
    get_settings.cache_clear()
    pools = []
    original = main.SQLiteConnectionPool

    def track_pool(*args):
        pool = original(*args)
        pools.append(pool)
        return pool

    def fail_repository(*args, **kwargs):
        raise sqlite3.OperationalError("simulated schema failure")

    monkeypatch.setattr(main, "SQLiteConnectionPool", track_pool)
    monkeypatch.setattr(main, "SQLiteVehicleRepository", fail_repository)
    try:
        with pytest.raises(sqlite3.OperationalError, match="simulated schema failure"):
            with TestClient(create_app()):
                pytest.fail("El arranque debe fallar")
        with pytest.raises(RuntimeError, match="cerrado"):
            with pools[0].connection():
                pytest.fail("No debe filtrar conexiones si falla el arranque")
    finally:
        get_settings.cache_clear()


def test_pooled_confirmation_failure_rolls_back_all_changes_and_sequence(tmp_path):
    path = tmp_path / "atomic.db"
    vehicle = VehicleRecord("AB123CD", "Toyota", "Corolla", "M123", "C456", 2020)
    with closing(SQLiteConnectionPool(path, 2)) as pool:
        vehicles = SQLiteVehicleRepository(path, pool=pool)
        documents = SQLiteDocumentRepository(path, pool=pool)
        documents.save_pending(DocumentRecord("atomic", "titulo.pdf"))
        documents.review("atomic", vehicle)
        with pool.connection() as connection:
            connection.execute("""
                CREATE TRIGGER fail_history BEFORE INSERT ON history_events
                WHEN NEW.tipo_evento = 'documento_registrado'
                BEGIN SELECT RAISE(ABORT, 'simulated history failure'); END
            """)
        with pytest.raises(sqlite3.IntegrityError, match="simulated history failure"):
            documents.confirm("atomic", vehicle)
        assert vehicles.list_all() == []
        assert documents.list_all()[0].estado == "revisado"
        assert len(documents.history_repository.list_all()) == 2
        with pool.connection() as connection:
            connection.execute("DROP TRIGGER fail_history")
        assert documents.confirm("atomic", vehicle).numero_registro == 1
        assert len(documents.history_repository.list_all()) == 3
