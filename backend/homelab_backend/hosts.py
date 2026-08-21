"""Persistent host inventory service."""

import sqlite3
from datetime import UTC, datetime
from uuid import UUID, uuid4

from .database import Database
from .models import Host, HostCreate, HostPatch

_SELECT = (
    "SELECT id, name, address, port, username, package_provider, "
    "distribution, distribution_version, kernel, updates, security_updates, "
    "reboot_required, status, checked_at, created_at, updated_at FROM hosts"
)


class DuplicateHostError(Exception):
    """Raised when a connection identity already exists."""


class HostRepository:
    """Manage stable host identities without exposing SQLite to the API."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def async_create(self, data: HostCreate) -> Host:
        """Create one host with a generated UUID."""
        now = datetime.now(UTC)
        host = Host(
            id=uuid4(),
            created_at=now,
            updated_at=now,
            **data.model_dump(),
        )
        try:
            await self._database.async_execute(
                "INSERT INTO hosts "
                "(id, name, address, port, username, package_provider, "
                "created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                _values(host),
            )
        except sqlite3.IntegrityError as err:
            raise DuplicateHostError(
                "A host with this connection already exists"
            ) from err
        return host

    async def async_list(self) -> tuple[Host, ...]:
        """List hosts in deterministic display order."""
        rows = await self._database.async_fetch_all(f"{_SELECT} ORDER BY name, id")
        return tuple(_host_from_row(row) for row in rows)

    async def async_get(self, host_id: UUID) -> Host | None:
        """Return one host by stable identity."""
        row = await self._database.async_fetch_one(
            f"{_SELECT} WHERE id = ?", (str(host_id),)
        )
        return _host_from_row(row) if row is not None else None

    async def async_patch(self, host_id: UUID, patch: HostPatch) -> Host | None:
        """Update mutable fields while preserving the UUID."""
        current = await self.async_get(host_id)
        if current is None:
            return None
        values = current.model_dump()
        values.update(patch.model_dump(exclude_none=True))
        values["updated_at"] = datetime.now(UTC)
        updated = Host.model_validate(values)
        try:
            await self._database.async_execute(
                "UPDATE hosts SET name = ?, address = ?, port = ?, username = ?, "
                "package_provider = ?, updated_at = ? WHERE id = ?",
                (
                    updated.name,
                    updated.address,
                    updated.port,
                    updated.username,
                    updated.package_provider,
                    updated.updated_at.isoformat(),
                    str(updated.id),
                ),
            )
        except sqlite3.IntegrityError as err:
            raise DuplicateHostError(
                "A host with this connection already exists"
            ) from err
        return updated

    async def async_delete(self, host_id: UUID) -> bool:
        """Delete one host and report whether it existed."""
        return bool(
            await self._database.async_execute(
                "DELETE FROM hosts WHERE id = ?", (str(host_id),)
            )
        )

    async def async_update_status(
        self,
        host_id: UUID,
        *,
        distribution: str | None,
        distribution_version: str | None,
        kernel: str | None,
        updates: int,
        security_updates: int,
        reboot_required: bool,
        status: str,
        checked_at: datetime,
    ) -> None:
        """Persist one normalized status snapshot."""
        await self._database.async_execute(
            "UPDATE hosts SET distribution = ?, distribution_version = ?, "
            "kernel = ?, updates = ?, security_updates = ?, reboot_required = ?, "
            "status = ?, checked_at = ?, updated_at = ? WHERE id = ?",
            (
                distribution,
                distribution_version,
                kernel,
                updates,
                security_updates,
                int(reboot_required),
                status,
                checked_at.isoformat(),
                datetime.now(UTC).isoformat(),
                str(host_id),
            ),
        )


def _values(host: Host) -> tuple[object, ...]:
    return (
        str(host.id),
        host.name,
        host.address,
        host.port,
        host.username,
        host.package_provider,
        host.created_at.isoformat(),
        host.updated_at.isoformat(),
    )


def _host_from_row(row: sqlite3.Row) -> Host:
    return Host(
        id=UUID(row["id"]),
        name=row["name"],
        address=row["address"],
        port=row["port"],
        username=row["username"],
        package_provider=row["package_provider"],
        distribution=row["distribution"],
        distribution_version=row["distribution_version"],
        kernel=row["kernel"],
        updates=row["updates"],
        security_updates=row["security_updates"],
        reboot_required=bool(row["reboot_required"]),
        status=row["status"],
        checked_at=(
            datetime.fromisoformat(row["checked_at"])
            if row["checked_at"] is not None
            else None
        ),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )
