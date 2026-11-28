"""Persistent host inventory service."""

import json
import sqlite3
from datetime import UTC, datetime
from uuid import UUID, uuid4

from .database import Database
from .models import (
    Host,
    HostCreate,
    HostPatch,
    HostWebsite,
    PackageInfo,
    PackageSourceStatus,
    PacmanReview,
)
from .policy.application import PolicyGuard
from .policy.domain import Permission
from .policy.store import policy_for

_SELECT = (
    "SELECT id, name, address, port, username, package_provider, "
    "distribution, distribution_version, kernel, updates, security_updates, "
    "reboot_required, status, checked_at, created_at, updated_at, "
    "websites_json, packages_json, security_known, reboot_known, "
    "package_scopes_json, package_sources_json, package_observations_json FROM hosts"
)


class DuplicateHostError(Exception):
    """Raised when a connection identity already exists."""


class HostBusyError(DuplicateHostError):
    """A running job holds the persisted connection identity."""


class HostRepository:
    """Manage stable host identities without exposing SQLite to the API."""

    def __init__(
        self, database: Database, *, policy: PolicyGuard | None = None
    ) -> None:
        self._database = database
        self._policy = policy or policy_for(database)
        # New package rows are disposable observations, not a persisted catalog.
        self._pacman_reviews: dict[UUID, tuple[datetime, PacmanReview]] = {}
        self._package_cache: dict[UUID, tuple[datetime, tuple[PackageInfo, ...]]] = {}

    async def async_create(self, data: HostCreate) -> Host:
        """Create one host with a generated UUID."""
        await self._policy.async_require(Permission.HOST_WRITE)
        now = datetime.now(UTC)
        host = Host(
            id=uuid4(),
            created_at=now,
            updated_at=now,
            **data.model_dump(),
            security_updates=0 if data.package_provider == "debian_apt" else None,
            reboot_required=False if data.package_provider == "debian_apt" else None,
        )
        try:
            await self._database.async_execute(
                "INSERT INTO hosts "
                "(id, name, address, port, username, package_provider, "
                "created_at, updated_at, websites_json, packages_json, "
                "security_known, reboot_known, package_sources_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
        return tuple(self._cached(_host_from_row(row)) for row in rows)

    async def async_get(self, host_id: UUID) -> Host | None:
        """Return one host by stable identity."""
        row = await self._database.async_fetch_one(
            f"{_SELECT} WHERE id = ?", (str(host_id),)
        )
        return self._cached(_host_from_row(row)) if row is not None else None

    def _cached(self, host: Host) -> Host:
        cached = self._package_cache.get(host.id)
        if cached is not None and cached[0] == host.checked_at:
            return host.model_copy(update={"packages": cached[1]})
        return host

    def pacman_review(self, host: Host) -> PacmanReview | None:
        cached = self._pacman_reviews.get(host.id)
        if cached is not None and cached[0] == host.checked_at and host.status == "ok":
            return cached[1]
        return None

    async def async_patch(self, host_id: UUID, patch: HostPatch) -> Host | None:
        """Update mutable fields while preserving the UUID."""
        await self._policy.async_require(Permission.HOST_WRITE)
        current = await self.async_get(host_id)
        if current is None:
            return None
        values = current.model_dump()
        values.update(patch.model_dump(exclude_none=True))
        if "package_sources" in patch.model_fields_set:
            values["package_sources"] = patch.package_sources
        values["updated_at"] = datetime.now(UTC)
        provider_changed = (
            values["package_provider"] != current.package_provider
            or values["package_sources"] != current.package_sources
        )
        if provider_changed:
            values.update(
                checked_at=None,
                security_updates=None,
                reboot_required=None,
                status="stale",
                packages=(),
                package_scopes=(),
                package_observations=(),
            )
        updated = Host.model_validate(values)
        try:
            await self._database.async_execute(
                "UPDATE hosts SET name = ?, address = ?, port = ?, username = ?, "
                "package_provider = ?, updated_at = ?, websites_json = ?, "
                "packages_json = CASE WHEN ? THEN '[]' ELSE packages_json END, "
                "checked_at = CASE WHEN ? THEN NULL ELSE checked_at END, "
                "status = CASE WHEN ? THEN 'stale' ELSE status END, "
                "security_known = CASE WHEN ? THEN 0 ELSE security_known END, "
                "reboot_known = CASE WHEN ? THEN 0 ELSE reboot_known END, "
                "package_scopes_json = CASE WHEN ? THEN '[]' "
                "ELSE package_scopes_json END, "
                "package_sources_json=?, "
                "package_observations_json=CASE WHEN ? THEN NULL "
                "ELSE package_observations_json END "
                "WHERE id = ?",
                (
                    updated.name,
                    updated.address,
                    updated.port,
                    updated.username,
                    updated.package_provider,
                    updated.updated_at.isoformat(),
                    json.dumps([
                        site.model_dump(mode="json") for site in updated.websites
                    ]),
                    *([provider_changed] * 6),
                    json.dumps(updated.package_sources)
                    if updated.package_sources is not None
                    else None,
                    provider_changed,
                    str(updated.id),
                ),
            )
        except sqlite3.IntegrityError as err:
            if str(err) == "host_execution_busy":
                raise HostBusyError(
                    "Host has running work; wait before changing its connection"
                ) from None
            raise DuplicateHostError(
                "A host with this connection already exists"
            ) from err
        if (
            current.address,
            current.port,
            current.username,
            current.package_provider,
            current.package_sources,
        ) != (
            updated.address,
            updated.port,
            updated.username,
            updated.package_provider,
            updated.package_sources,
        ):
            self._pacman_reviews.pop(host_id, None)
            await self._database.async_execute(
                "DELETE FROM task_checks WHERE host_id = ?", (str(host_id),)
            )
        if provider_changed:
            self._package_cache.pop(host_id, None)
        return updated

    async def async_delete(self, host_id: UUID) -> bool:
        """Delete one host and report whether it existed."""
        await self._policy.async_require(Permission.HOST_WRITE)
        try:
            deleted = bool(
                await self._database.async_execute(
                    "DELETE FROM hosts WHERE id = ?", (str(host_id),)
                )
            )
            if deleted:
                self._pacman_reviews.pop(host_id, None)
                self._package_cache.pop(host_id, None)
            return deleted
        except sqlite3.IntegrityError as err:
            if str(err) == "host_execution_busy":
                raise HostBusyError(
                    "Host has running work; wait before removing it"
                ) from None
            raise

    async def async_mark_stale(self, host_id: UUID) -> None:
        """Preserve measured values while marking an uncertain package snapshot."""
        await self._policy.async_require(Permission.HOST_STATUS)
        await self._database.async_execute(
            "UPDATE hosts SET status='stale' WHERE id=?", (str(host_id),)
        )

    async def async_update_status(
        self,
        host_id: UUID,
        *,
        distribution: str | None,
        distribution_version: str | None,
        kernel: str | None,
        updates: int,
        security_updates: int | None,
        reboot_required: bool | None,
        status: str,
        checked_at: datetime,
        packages: tuple[PackageInfo, ...],
        package_scopes: tuple[str, ...] | None = None,
        package_observations: tuple[PackageSourceStatus, ...] = (),
        pacman_review: PacmanReview | None = None,
    ) -> None:
        """Persist one normalized status snapshot."""
        await self._policy.async_require(Permission.HOST_STATUS)
        await self._database.async_execute(
            "UPDATE hosts SET distribution = ?, distribution_version = ?, "
            "kernel = ?, updates = ?, security_updates = ?, reboot_required = ?, "
            "status = ?, checked_at = ?, updated_at = ?, "
            "security_known = ?, reboot_known = ?, package_scopes_json = ?, "
            "package_observations_json = ? "
            "WHERE id = ?",
            (
                distribution,
                distribution_version,
                kernel,
                updates,
                security_updates if security_updates is not None else 0,
                int(reboot_required) if reboot_required is not None else 0,
                status,
                checked_at.isoformat(),
                datetime.now(UTC).isoformat(),
                int(security_updates is not None),
                int(reboot_required is not None),
                json.dumps(package_scopes) if package_scopes is not None else None,
                json.dumps([
                    item.model_dump(mode="json") for item in package_observations
                ]),
                str(host_id),
            ),
        )
        self._package_cache[host_id] = (checked_at, packages)
        if pacman_review is not None:
            self._pacman_reviews[host_id] = (checked_at, pacman_review)
        else:
            self._pacman_reviews.pop(host_id, None)


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
        json.dumps([site.model_dump(mode="json") for site in host.websites]),
        json.dumps([package.model_dump(mode="json") for package in host.packages]),
        int(host.security_updates is not None),
        int(host.reboot_required is not None),
        json.dumps(host.package_sources) if host.package_sources is not None else None,
    )


def _host_from_row(row: sqlite3.Row) -> Host:
    return Host(
        id=UUID(row["id"]),
        name=row["name"],
        address=row["address"],
        port=row["port"],
        username=row["username"],
        package_provider=row["package_provider"],
        package_sources=tuple(json.loads(row["package_sources_json"]))
        if row["package_sources_json"] is not None
        else None,
        package_observations=tuple(
            PackageSourceStatus.model_validate(item)
            for item in json.loads(row["package_observations_json"] or "[]")
        ),
        websites=tuple(
            HostWebsite.model_validate(site)
            for site in json.loads(row["websites_json"])
        ),
        packages=tuple(
            PackageInfo.model_validate(package)
            for package in json.loads(row["packages_json"])
        )
        if row["package_observations_json"] is None
        else (),
        distribution=row["distribution"],
        distribution_version=row["distribution_version"],
        kernel=row["kernel"],
        updates=row["updates"],
        security_updates=row["security_updates"] if row["security_known"] else None,
        reboot_required=bool(row["reboot_required"]) if row["reboot_known"] else None,
        package_scopes=tuple(json.loads(row["package_scopes_json"]))
        if row["package_scopes_json"]
        else None,
        status=row["status"],
        checked_at=(
            datetime.fromisoformat(row["checked_at"])
            if row["checked_at"] is not None
            else None
        ),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )
