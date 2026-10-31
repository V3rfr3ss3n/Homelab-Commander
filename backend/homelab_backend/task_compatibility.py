"""Explicit compatibility checks and persistent host/task assignment policy."""

import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from .automation import AutomationExecutionError, AutomationExecutor
from .custom_tasks import CustomTaskRepository
from .database import Database
from .hosts import HostRepository
from .models import CompatibilityState, CustomTask, Host, TaskCompatibility

CHECK_LIFETIME = timedelta(hours=24)


def _fingerprint(task: CustomTask, host: Host) -> str:
    values = (
        host.address,
        host.port,
        host.username,
        host.package_provider,
        task.mode,
        task.argv,
        task.shell_command,
        task.requirements.model_dump(),
    )
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


class TaskCompatibilityService:
    """Fail closed on unknown, stale or incompatible prerequisite evidence."""

    def __init__(
        self,
        database: Database,
        tasks: CustomTaskRepository,
        hosts: HostRepository,
        executor: AutomationExecutor,
    ) -> None:
        self._database = database
        self._tasks = tasks
        self._hosts = hosts
        self._executor = executor

    async def async_pair(self, task_id: UUID, host_id: UUID) -> tuple[CustomTask, Host]:
        task = await self._tasks.async_get(task_id)
        host = await self._hosts.async_get(host_id)
        if task is None or host is None:
            raise KeyError("Task or host not found")
        return task, host

    async def async_get(self, task_id: UUID, host_id: UUID) -> TaskCompatibility:
        task, host = await self.async_pair(task_id, host_id)
        assignment = await self._database.async_fetch_one(
            "SELECT enabled FROM task_assignments WHERE task_id = ? AND host_id = ?",
            (str(task_id), str(host_id)),
        )
        result = TaskCompatibility(task_id=task_id, host_id=host_id)
        row = await self._database.async_fetch_one(
            "SELECT fingerprint, result_json FROM task_checks WHERE task_id = "
            "? AND host_id = ?",
            (str(task_id), str(host_id)),
        )
        if row is not None and row["fingerprint"] == _fingerprint(task, host):
            stored = TaskCompatibility.model_validate_json(row["result_json"])
            if (
                stored.checked_at is not None
                and timedelta(0)
                <= datetime.now(UTC) - stored.checked_at
                < CHECK_LIFETIME
            ):
                result = stored
        return result.model_copy(
            update={
                "assigned": assignment is not None,
                "enabled": bool(assignment and assignment["enabled"]),
            }
        )

    async def async_check(self, task_id: UUID, host_id: UUID) -> TaskCompatibility:
        task, host = await self.async_pair(task_id, host_id)
        fingerprint = _fingerprint(task, host)
        reasons: list[str] = []
        state = CompatibilityState.SUITABLE
        try:
            facts = await asyncio.wait_for(
                self._executor.async_probe(task, host), timeout=30
            )
            requirements = task.requirements
            if (
                requirements.distributions
                and facts.distribution.lower() not in requirements.distributions
            ):
                reasons.append("Distribution not supported by this task")
            if requirements.versions and facts.version not in requirements.versions:
                reasons.append("System version not supported by this task")
            reasons.extend(
                f"Missing program: {name}" for name in facts.missing_programs
            )
            reasons.extend(
                f"Missing package: {name}" for name in facts.missing_packages
            )
            if reasons:
                state = CompatibilityState.UNSUITABLE
        except AutomationExecutionError, TimeoutError:
            state = CompatibilityState.FAILED
            reasons.append("Could not verify SSH, Python or required privileges")
        result = TaskCompatibility(
            task_id=task_id,
            host_id=host_id,
            state=state,
            reasons=tuple(reasons),
            checked_at=datetime.now(UTC),
        )
        # Store the inputs actually checked: concurrent edits invalidate this result.
        await self._database.async_execute(
            "INSERT OR REPLACE INTO "
            "task_checks(task_id,host_id,fingerprint,result_json) VALUES (?,?,?,?)",
            (str(task_id), str(host_id), fingerprint, result.model_dump_json()),
        )
        return await self.async_get(task_id, host_id)

    async def async_assign(
        self, task_id: UUID, host_id: UUID, *, enabled: bool
    ) -> TaskCompatibility:
        result = await self.async_get(task_id, host_id)
        if (
            enabled or not result.assigned
        ) and result.state is not CompatibilityState.SUITABLE:
            raise ValueError(
                "Check task compatibility successfully before assigning or enabling it"
            )
        await self._database.async_execute(
            "INSERT INTO task_assignments(task_id,host_id,enabled) VALUES (?,?,?) "
            "ON CONFLICT(task_id,host_id) DO UPDATE SET enabled=excluded.enabled",
            (str(task_id), str(host_id), int(enabled)),
        )
        return await self.async_get(task_id, host_id)

    async def async_unassign(self, task_id: UUID, host_id: UUID) -> None:
        await self.async_pair(task_id, host_id)
        await self._database.async_execute(
            "DELETE FROM task_assignments WHERE task_id = ? AND host_id = ?",
            (str(task_id), str(host_id)),
        )

    async def async_require(
        self, task_id: UUID, host_id: UUID, *, fresh: bool = False
    ) -> tuple[CustomTask, Host]:
        task, host = await self.async_pair(task_id, host_id)
        result = await self.async_get(task_id, host_id)
        if not task.enabled or not result.assigned or not result.enabled:
            raise ValueError("Task is disabled or not assigned to this host")
        if fresh:
            fingerprint = _fingerprint(task, host)
            await self.async_check(task_id, host_id)
            # Dispatch immutable inputs matching the probe, even if edits overlap it.
            result = await self.async_get(task_id, host_id)
            task, host = await self.async_pair(task_id, host_id)
            if not task.enabled or not result.assigned or not result.enabled:
                raise ValueError("Task is disabled or not assigned to this host")
            if _fingerprint(task, host) != fingerprint:
                raise ValueError(
                    "Task or connection changed during compatibility check"
                )
        if result.state is not CompatibilityState.SUITABLE:
            raise ValueError("A successful current compatibility check is required")
        return task, host
