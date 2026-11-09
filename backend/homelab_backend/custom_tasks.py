"""Persistent custom task definitions and shell security policy."""

import json
import sqlite3
from datetime import UTC, datetime
from uuid import UUID, uuid4

from .database import Database
from .models import (
    CustomTask,
    CustomTaskCreate,
    CustomTaskMode,
    CustomTaskPatch,
    TaskRequirements,
)

_SELECT = (
    "SELECT id, name, description, mode, argv_json, shell_command, enabled, "
    "created_at, updated_at, requirements_json FROM custom_tasks"
)


class ShellTasksDisabledError(Exception):
    """Raised when shell semantics are disabled by backend policy."""


class CustomTaskRepository:
    """Manage validated task definitions with stable UUID identity."""

    def __init__(self, database: Database, *, allow_shell: bool) -> None:
        self._database = database
        self._allow_shell = allow_shell

    async def async_create(self, data: CustomTaskCreate) -> CustomTask:
        self._check_shell(data.mode)
        now = datetime.now(UTC)
        task = CustomTask(
            id=uuid4(), created_at=now, updated_at=now, **data.model_dump()
        )
        await self._database.async_execute(
            "INSERT INTO custom_tasks "
            "(id, name, description, mode, argv_json, shell_command, enabled, "
            "created_at, updated_at, requirements_json) VALUES (?, ?, ?, ?, "
            "?, ?, ?, ?, ?, ?)",
            _values(task),
        )
        return task

    async def async_list(self) -> tuple[CustomTask, ...]:
        rows = await self._database.async_fetch_all(f"{_SELECT} ORDER BY name, id")
        return tuple([await self._with_hosts(_from_row(row)) for row in rows])

    async def async_get(self, task_id: UUID) -> CustomTask | None:
        row = await self._database.async_fetch_one(
            f"{_SELECT} WHERE id = ?", (str(task_id),)
        )
        return await self._with_hosts(_from_row(row)) if row is not None else None

    async def async_patch(
        self, task_id: UUID, patch: CustomTaskPatch
    ) -> CustomTask | None:
        current = await self.async_get(task_id)
        if current is None:
            return None
        values = current.model_dump(
            include={
                "name",
                "description",
                "mode",
                "argv",
                "shell_command",
                "enabled",
                "requirements",
            }
        )
        values.update(patch.model_dump(exclude_unset=True))
        validated = CustomTaskCreate.model_validate(values)
        self._check_shell(validated.mode)
        updated = CustomTask(
            id=current.id,
            created_at=current.created_at,
            updated_at=datetime.now(UTC),
            **validated.model_dump(),
        )
        await self._database.async_execute(
            "UPDATE custom_tasks SET name = ?, description = ?, mode = ?, "
            "argv_json = ?, shell_command = ?, enabled = ?, updated_at = ?, "
            "requirements_json = ? "
            "WHERE id = ?",
            (
                updated.name,
                updated.description,
                updated.mode,
                json.dumps(updated.argv) if updated.argv is not None else None,
                updated.shell_command,
                int(updated.enabled),
                updated.updated_at.isoformat(),
                updated.requirements.model_dump_json(),
                str(updated.id),
            ),
        )
        if (
            current.requirements,
            current.mode,
            current.argv,
            current.shell_command,
        ) != (updated.requirements, updated.mode, updated.argv, updated.shell_command):
            await self._database.async_execute(
                "DELETE FROM task_checks WHERE task_id = ?", (str(task_id),)
            )
        return await self._with_hosts(updated)

    async def async_delete(self, task_id: UUID) -> bool:
        return bool(
            await self._database.async_execute(
                "DELETE FROM custom_tasks WHERE id = ?", (str(task_id),)
            )
        )

    async def _with_hosts(self, task: CustomTask) -> CustomTask:
        rows = await self._database.async_fetch_all(
            "SELECT host_id FROM task_assignments WHERE task_id = ? AND "
            "enabled = 1 ORDER BY host_id",
            (str(task.id),),
        )
        return task.model_copy(
            update={"host_ids": tuple(UUID(row["host_id"]) for row in rows)}
        )

    def _check_shell(self, mode: CustomTaskMode) -> None:
        if mode is CustomTaskMode.SHELL and not self._allow_shell:
            raise ShellTasksDisabledError("Shell custom tasks are disabled")


def _values(task: CustomTask) -> tuple[object, ...]:
    return (
        str(task.id),
        task.name,
        task.description,
        task.mode,
        json.dumps(task.argv) if task.argv is not None else None,
        task.shell_command,
        int(task.enabled),
        task.created_at.isoformat(),
        task.updated_at.isoformat(),
        task.requirements.model_dump_json(),
    )


def _from_row(row: sqlite3.Row) -> CustomTask:
    raw_argv = json.loads(row["argv_json"]) if row["argv_json"] is not None else None
    argv = tuple(raw_argv) if isinstance(raw_argv, list) else None
    return CustomTask(
        id=UUID(row["id"]),
        name=row["name"],
        description=row["description"],
        mode=CustomTaskMode(row["mode"]),
        argv=argv,
        shell_command=row["shell_command"],
        enabled=bool(row["enabled"]),
        requirements=TaskRequirements.model_validate_json(row["requirements_json"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )
