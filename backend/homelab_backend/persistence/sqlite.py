"""Small asynchronous boundary around SQLite and schema migrations."""

import asyncio
import sqlite3
from collections.abc import Callable, Sequence
from contextlib import closing
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import TypeVar

from .migrations import MIGRATIONS

T = TypeVar("T")

# Serialize first-time WAL setup across Database objects in this process. All
# waiting happens in the worker thread; SQL transactions protect data/versioning.
_SCHEMA_LOCK = Lock()


def _timestamp(value: str) -> float:
    """Convert persisted timezone-aware ISO dates without SQLite date modifiers."""
    return datetime.fromisoformat(value).timestamp()


class Database:
    """Serialize schema changes while keeping request I/O off the event loop."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._migration_lock = asyncio.Lock()

    async def async_migrate(self) -> None:
        """Apply all pending schema migrations transactionally."""
        async with self._migration_lock:
            await asyncio.to_thread(self._migrate)

    async def async_execute(
        self, statement: str, parameters: Sequence[object] = ()
    ) -> int:
        """Execute a write and return the affected row count."""
        return await asyncio.to_thread(self._execute, statement, parameters)

    async def async_fetch_one(
        self, statement: str, parameters: Sequence[object] = ()
    ) -> sqlite3.Row | None:
        """Fetch at most one row."""
        return await asyncio.to_thread(self._fetch_one, statement, parameters)

    async def async_fetch_all(
        self, statement: str, parameters: Sequence[object] = ()
    ) -> list[sqlite3.Row]:
        """Fetch a detached row list."""
        return await asyncio.to_thread(self._fetch_all, statement, parameters)

    async def async_transaction(
        self, operation: Callable[[sqlite3.Connection], T]
    ) -> T:
        """Run a synchronous callback in one immediate transaction."""
        return await asyncio.to_thread(self._transaction, operation)

    def _connect(self) -> sqlite3.Connection:
        self._path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        connection = sqlite3.connect(self._path, timeout=10)
        try:
            connection.row_factory = sqlite3.Row
            # SQLite before 3.42 silently returns NULL for unixepoch(..., 'subsec').
            # Parse our typed ISO timestamps consistently, including microseconds and
            # UTC offsets, without requiring a system SQLite upgrade or data rewrite.
            connection.create_function(
                "hlc_timestamp", 1, _timestamp, deterministic=True
            )
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
        except Exception:
            connection.close()
            raise
        return connection

    def _migrate(self) -> None:
        with _SCHEMA_LOCK, closing(self._connect()) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version INTEGER PRIMARY KEY)"
            )
            for version, migration in enumerate(MIGRATIONS, start=1):
                with connection:
                    connection.execute("BEGIN IMMEDIATE")
                    if connection.execute(
                        "SELECT 1 FROM schema_migrations WHERE version=?", (version,)
                    ).fetchone():
                        continue
                    # executescript commits a prior transaction implicitly. Execute
                    # complete statements ourselves so DDL, backfill and version
                    # marker share the lock and rollback boundary, including triggers.
                    statement = ""
                    for character in migration:
                        statement += character
                        if character == ";" and sqlite3.complete_statement(statement):
                            connection.execute(statement)
                            statement = ""
                    if statement.strip():
                        connection.execute(statement)
                    connection.execute(
                        "INSERT INTO schema_migrations(version) VALUES (?)", (version,)
                    )

    def _execute(self, statement: str, parameters: Sequence[object]) -> int:
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(statement, parameters)
            return cursor.rowcount

    def _fetch_one(
        self, statement: str, parameters: Sequence[object]
    ) -> sqlite3.Row | None:
        with closing(self._connect()) as connection:
            row = connection.execute(statement, parameters).fetchone()
            return row if isinstance(row, sqlite3.Row) else None

    def _fetch_all(
        self, statement: str, parameters: Sequence[object]
    ) -> list[sqlite3.Row]:
        with closing(self._connect()) as connection:
            return list(connection.execute(statement, parameters).fetchall())

    def _transaction(self, operation: Callable[[sqlite3.Connection], T]) -> T:
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            return operation(connection)
