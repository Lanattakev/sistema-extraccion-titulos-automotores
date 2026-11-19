"""src/infrastructure/persistence/sqlite_connections.py"""

import sqlite3
from collections.abc import Generator
from contextlib import closing, contextmanager
from pathlib import Path
from threading import Condition


def require_safe_sqlite() -> None:
    """Rechaza motores afectados por el fallo WAL-reset antes de abrir archivos."""
    version = sqlite3.sqlite_version_info
    if not (
        version >= (3, 51, 3)
        or (3, 50, 7) <= version < (3, 51, 0)
        or (3, 44, 6) <= version < (3, 45, 0)
    ):
        raise RuntimeError(
            f"SQLite {sqlite3.sqlite_version} no es seguro para WAL concurrente. "
            "Actualice el runtime a SQLite >= 3.51.3 (o 3.50.7/3.44.6 corregidos)."
        )


def _open_connection(db_path: str | Path) -> sqlite3.Connection:
    require_safe_sqlite()
    connection = sqlite3.connect(str(db_path), timeout=30, check_same_thread=False)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute("PRAGMA foreign_keys = ON")
        mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
        if mode.lower() != "wal":
            raise ValueError("La base debe admitir WAL en un archivo SQLite local.")
        connection.execute("PRAGMA synchronous = NORMAL")
    except BaseException:
        connection.close()
        raise
    return connection


class SQLiteConnectionPool:
    """Pool acotado por proceso; ninguna conexion se presta a dos operaciones."""

    def __init__(
        self, db_path: str | Path, pool_size: int = 4, *, acquire_timeout: float = 30
    ) -> None:
        if pool_size < 1 or acquire_timeout <= 0:
            raise ValueError("El tamano del pool y su tiempo de espera deben ser positivos.")
        self.database_path = Path(db_path).resolve()
        self._condition = Condition()
        self._closed = False
        self._acquire_timeout = acquire_timeout
        self._available: list[sqlite3.Connection] = []
        try:
            for _ in range(pool_size):
                self._available.append(_open_connection(db_path))
        except BaseException:
            self.close()
            raise

    def _acquire(self) -> sqlite3.Connection:
        with self._condition:
            ready = self._condition.wait_for(
                lambda: self._closed or bool(self._available), timeout=self._acquire_timeout
            )
            if self._closed:
                raise RuntimeError("El pool SQLite esta cerrado.")
            if not ready:
                raise TimeoutError("Se agoto la espera por una conexion SQLite disponible.")
            return self._available.pop()

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        connection = self._acquire()
        try:
            with connection:
                yield connection
        finally:
            with self._condition:
                close_connection = self._closed
                if not close_connection:
                    self._available.append(connection)
                    self._condition.notify()
            if close_connection:
                connection.close()

    def close(self) -> None:
        """Cierra ociosas y despierta esperas; los prestamos activos cierran al retornar."""
        with self._condition:
            self._closed = True
            idle, self._available = self._available, []
            self._condition.notify_all()
        for connection in idle:
            connection.close()


@contextmanager
def sqlite_connection(
    db_path: str | Path, pool: SQLiteConnectionPool | None = None
) -> Generator[sqlite3.Connection, None, None]:
    """Comparte el pool inyectado; los repositorios independientes no retienen handles."""
    if pool is not None:
        if Path(db_path).resolve() != pool.database_path:
            raise ValueError("El pool pertenece a otra base SQLite.")
        with pool.connection() as connection:
            yield connection
    else:
        with closing(_open_connection(db_path)) as connection, connection:
            yield connection
