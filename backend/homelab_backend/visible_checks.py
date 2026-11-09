"""Opt-out status checks requested by a visible management UI, never a scheduler."""

import sqlite3
from datetime import UTC, datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from .database import Database
from .hosts import HostRepository
from .jobs import JobManager
from .models import Job, JobAction

CHECK_INTERVAL_SECONDS = 300


class HostCheckPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    enabled: bool = True


class VisibleChecks:
    """Persist preference/cooldown; clients explicitly request eligible host checks."""

    def __init__(
        self, database: Database, hosts: HostRepository, jobs: JobManager
    ) -> None:
        self._database = database
        self._hosts = hosts
        self._jobs = jobs

    async def async_preferences(self) -> HostCheckPreferences:
        row = await self._database.async_fetch_one(
            "SELECT auto_check_enabled FROM ui_preferences WHERE id=1"
        )
        return HostCheckPreferences(enabled=bool(row and row["auto_check_enabled"]))

    async def async_update(
        self, preferences: HostCheckPreferences
    ) -> HostCheckPreferences:
        await self._database.async_execute(
            "UPDATE ui_preferences SET auto_check_enabled=? WHERE id=1",
            (int(preferences.enabled),),
        )
        return preferences

    async def async_check(self) -> tuple[Job, ...]:
        if not (await self.async_preferences()).enabled:
            return ()
        now = datetime.now(UTC)
        jobs: list[Job] = []
        for host in await self._hosts.async_list():
            if await self._claim(host.id, now):
                try:
                    jobs.append(
                        await self._jobs.async_enqueue(JobAction.CHECK_UPDATES, host.id)
                    )
                except KeyError:
                    # A host removed after the claim must never be contacted.
                    continue
        return tuple(jobs)

    async def _claim(self, host_id: UUID, now: datetime) -> bool:
        def claim(connection: sqlite3.Connection) -> bool:
            # Preference, host freshness, active work and shared cooldown are atomic.
            enabled = connection.execute(
                "SELECT auto_check_enabled FROM ui_preferences WHERE id=1"
            ).fetchone()
            if not enabled[0]:
                return False
            host = connection.execute(
                "SELECT checked_at FROM hosts WHERE id=?", (str(host_id),)
            ).fetchone()
            if host is None:
                return False
            cutoff = now - timedelta(seconds=CHECK_INTERVAL_SECONDS)
            if host[0] is not None and datetime.fromisoformat(host[0]) > cutoff:
                return False
            active = connection.execute(
                "SELECT 1 FROM jobs WHERE host_id=? AND state IN "
                "('queued','running') LIMIT 1",
                (str(host_id),),
            ).fetchone()
            if active:
                return False
            prior = connection.execute(
                "SELECT requested_at FROM ui_auto_checks WHERE host_id=?",
                (str(host_id),),
            ).fetchone()
            if prior and datetime.fromisoformat(prior[0]) > cutoff:
                return False
            connection.execute(
                "INSERT INTO ui_auto_checks(host_id,requested_at) VALUES (?,?) "
                "ON CONFLICT(host_id) DO UPDATE SET requested_at=excluded.requested_at",
                (str(host_id), now.isoformat()),
            )
            return True

        return await self._database.async_transaction(claim)
