"""Small asynchronous boundary around SQLite and schema migrations."""

import asyncio
import sqlite3
from collections.abc import Callable, Sequence
from contextlib import closing
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")

_MIGRATIONS: tuple[str, ...] = (
    """
    CREATE TABLE hosts (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        address TEXT NOT NULL,
        port INTEGER NOT NULL CHECK (port BETWEEN 1 AND 65535),
        username TEXT NOT NULL,
        package_provider TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE UNIQUE INDEX hosts_address_user_port
        ON hosts(address, username, port);
    """,
    """
    ALTER TABLE hosts ADD COLUMN distribution TEXT;
    ALTER TABLE hosts ADD COLUMN distribution_version TEXT;
    ALTER TABLE hosts ADD COLUMN kernel TEXT;
    ALTER TABLE hosts ADD COLUMN updates INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE hosts ADD COLUMN security_updates INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE hosts ADD COLUMN reboot_required INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE hosts ADD COLUMN status TEXT;
    ALTER TABLE hosts ADD COLUMN checked_at TEXT;

    CREATE TABLE jobs (
        id TEXT PRIMARY KEY,
        action TEXT NOT NULL,
        host_id TEXT REFERENCES hosts(id) ON DELETE SET NULL,
        state TEXT NOT NULL,
        created_at TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT,
        error_code TEXT,
        reboot_required INTEGER,
        CHECK (state IN ('queued', 'running', 'success', 'failed'))
    );
    CREATE INDEX jobs_created_at ON jobs(created_at DESC);
    CREATE INDEX jobs_host_created ON jobs(host_id, created_at DESC);

    CREATE TABLE job_logs (
        job_id TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
        output TEXT NOT NULL,
        truncated INTEGER NOT NULL DEFAULT 0
    );
    """,
    """
    CREATE TABLE custom_tasks (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT NOT NULL,
        mode TEXT NOT NULL CHECK (mode IN ('command', 'shell')),
        argv_json TEXT,
        shell_command TEXT,
        enabled INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    ALTER TABLE jobs ADD COLUMN custom_task_id TEXT
        REFERENCES custom_tasks(id) ON DELETE SET NULL;
    """,
    """
    ALTER TABLE job_logs RENAME TO old_job_logs;
    ALTER TABLE jobs RENAME TO old_jobs;

    CREATE TABLE jobs (
        id TEXT PRIMARY KEY,
        action TEXT NOT NULL,
        host_id TEXT REFERENCES hosts(id) ON DELETE SET NULL,
        state TEXT NOT NULL,
        created_at TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT,
        exit_code INTEGER,
        error_code TEXT,
        reboot_required INTEGER,
        custom_task_id TEXT REFERENCES custom_tasks(id) ON DELETE SET NULL,
        CHECK (state IN ('queued', 'running', 'success', 'failed', 'cancelled'))
    );
    INSERT INTO jobs (
        id, action, host_id, state, created_at, started_at, finished_at,
        error_code, reboot_required, custom_task_id
    )
    SELECT id, action, host_id, state, created_at, started_at, finished_at,
        error_code, reboot_required, custom_task_id
    FROM old_jobs;

    CREATE TABLE job_logs (
        job_id TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
        output TEXT NOT NULL,
        truncated INTEGER NOT NULL DEFAULT 0
    );
    INSERT INTO job_logs(job_id, output, truncated)
        SELECT job_id, output, truncated FROM old_job_logs;

    DROP TABLE old_job_logs;
    DROP TABLE old_jobs;
    CREATE INDEX jobs_created_at ON jobs(created_at DESC);
    CREATE INDEX jobs_host_created ON jobs(host_id, created_at DESC);
    """,
)


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
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _migrate(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version INTEGER PRIMARY KEY)"
            )
            applied = {
                int(row[0])
                for row in connection.execute("SELECT version FROM schema_migrations")
            }
            for version, migration in enumerate(_MIGRATIONS, start=1):
                if version in applied:
                    continue
                connection.executescript(
                    f"BEGIN IMMEDIATE;\n{migration}\n"
                    f"INSERT INTO schema_migrations(version) VALUES ({version});\n"
                    "COMMIT;"
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
