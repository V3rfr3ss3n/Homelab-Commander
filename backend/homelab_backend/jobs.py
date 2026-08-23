"""Persistent asynchronous job queue and lifecycle service."""

import asyncio
import sqlite3
from contextlib import suppress
from datetime import UTC, datetime
from uuid import UUID, uuid4

from .automation import (
    AutomationExecutionError,
    AutomationExecutor,
    ExecutionResult,
)
from .custom_tasks import CustomTaskRepository
from .database import Database
from .hosts import HostRepository
from .models import Host, Job, JobAction, JobLog, JobState

MAX_JOB_LOG_BYTES = 64 * 1024
_MUTATING_ACTIONS = frozenset({JobAction.UPDATE, JobAction.REBOOT})
_SELECT = (
    "SELECT jobs.id, jobs.action, jobs.host_id, hosts.name AS host_name, jobs.state, "
    "jobs.created_at, jobs.started_at, jobs.finished_at, jobs.exit_code, "
    "jobs.error_code, jobs.reboot_required, jobs.custom_task_id, "
    "EXISTS(SELECT 1 FROM job_logs WHERE job_logs.job_id = jobs.id) "
    "AS log_available FROM jobs LEFT JOIN hosts ON hosts.id = jobs.host_id"
)


class JobRepository:
    """Persist queue state and bounded output independently of workers."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def async_create(
        self,
        action: JobAction,
        host_id: UUID,
        *,
        host_name: str | None = None,
        custom_task_id: UUID | None = None,
    ) -> Job:
        now = datetime.now(UTC)
        job = Job(
            id=uuid4(),
            action=action,
            host_id=host_id,
            host_name=host_name,
            custom_task_id=custom_task_id,
            state=JobState.QUEUED,
            created_at=now,
        )
        await self._database.async_execute(
            "INSERT INTO jobs "
            "(id, action, host_id, custom_task_id, state, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                str(job.id),
                job.action,
                str(host_id),
                str(custom_task_id) if custom_task_id is not None else None,
                job.state,
                now.isoformat(),
            ),
        )
        return job

    async def async_get(self, job_id: UUID) -> Job | None:
        row = await self._database.async_fetch_one(
            f"{_SELECT} WHERE jobs.id = ?", (str(job_id),)
        )
        return _job_from_row(row) if row is not None else None

    async def async_list(self, *, limit: int = 100) -> tuple[Job, ...]:
        rows = await self._database.async_fetch_all(
            f"{_SELECT} ORDER BY jobs.created_at DESC LIMIT ?", (limit,)
        )
        return tuple(_job_from_row(row) for row in rows)

    async def async_recover_queued(self) -> tuple[UUID, ...]:
        """Return queued work after safely recovering interrupted jobs."""
        await self._database.async_execute(
            "UPDATE jobs SET state = 'queued', started_at = NULL "
            "WHERE state = 'running'"
        )
        rows = await self._database.async_fetch_all(
            "SELECT id FROM jobs WHERE state = 'queued' ORDER BY created_at"
        )
        return tuple(UUID(row["id"]) for row in rows)

    async def async_claim(self, job_id: UUID) -> bool:
        return bool(
            await self._database.async_execute(
                "UPDATE jobs SET state = 'running', started_at = ? "
                "WHERE id = ? AND state = 'queued'",
                (datetime.now(UTC).isoformat(), str(job_id)),
            )
        )

    async def async_finish(
        self,
        job_id: UUID,
        *,
        state: JobState,
        output: str,
        truncated: bool,
        exit_code: int | None = None,
        error_code: str | None = None,
        reboot_required: bool | None = None,
    ) -> None:
        """Atomically store terminal state and its bounded output."""

        def finish(connection: sqlite3.Connection) -> None:
            connection.execute(
                "UPDATE jobs SET state = ?, finished_at = ?, exit_code = ?, "
                "error_code = ?, reboot_required = ? WHERE id = ?",
                (
                    state,
                    datetime.now(UTC).isoformat(),
                    exit_code,
                    error_code,
                    int(reboot_required) if reboot_required is not None else None,
                    str(job_id),
                ),
            )
            connection.execute(
                "INSERT OR REPLACE INTO job_logs(job_id, output, truncated) "
                "VALUES (?, ?, ?)",
                (str(job_id), output, int(truncated)),
            )

        await self._database.async_transaction(finish)

    async def async_log(self, job_id: UUID) -> JobLog | None:
        row = await self._database.async_fetch_one(
            "SELECT output, truncated FROM job_logs WHERE job_id = ?",
            (str(job_id),),
        )
        if row is None:
            return None
        return JobLog(
            job_id=job_id,
            output=row["output"],
            truncated=bool(row["truncated"]),
        )


class JobManager:
    """Run persistent jobs with bounded concurrency and per-host mutation locks."""

    def __init__(
        self,
        repository: JobRepository,
        hosts: HostRepository,
        custom_tasks: CustomTaskRepository,
        executor: AutomationExecutor,
        *,
        worker_count: int = 2,
    ) -> None:
        if worker_count < 1 or worker_count > 16:
            raise ValueError("worker_count must be between 1 and 16")
        self._repository = repository
        self._hosts = hosts
        self._custom_tasks = custom_tasks
        self._executor = executor
        self._worker_count = worker_count
        self._queue: asyncio.Queue[UUID] = asyncio.Queue()
        self._workers: list[asyncio.Task[None]] = []
        self._host_locks: dict[UUID, asyncio.Lock] = {}

    async def async_start(self) -> None:
        """Recover persistent work and start bounded workers."""
        for job_id in await self._repository.async_recover_queued():
            self._queue.put_nowait(job_id)
        self._workers = [
            asyncio.create_task(self._async_worker(), name=f"job-worker-{index}")
            for index in range(self._worker_count)
        ]

    async def async_stop(self) -> None:
        """Cancel workers without deleting persistent queued state."""
        for worker in self._workers:
            worker.cancel()
        for worker in self._workers:
            with suppress(asyncio.CancelledError):
                await worker
        self._workers.clear()

    async def async_enqueue(self, action: JobAction, host_id: UUID) -> Job:
        """Validate the exact target before creating persistent work."""
        host = await self._hosts.async_get(host_id)
        if host is None:
            raise KeyError("Host not found")
        job = await self._repository.async_create(action, host_id, host_name=host.name)
        self._queue.put_nowait(job.id)
        return job

    async def async_wait_idle(self) -> None:
        """Wait until all currently queued work has reached persistence."""
        await self._queue.join()

    async def async_enqueue_custom(self, task_id: UUID, host_id: UUID) -> Job:
        """Queue one enabled custom task with two validated identities."""
        host = await self._hosts.async_get(host_id)
        if host is None:
            raise KeyError("Host not found")
        task = await self._custom_tasks.async_get(task_id)
        if task is None:
            raise KeyError("Custom task not found")
        if not task.enabled:
            raise ValueError("Custom task is disabled")
        job = await self._repository.async_create(
            JobAction.CUSTOM_TASK,
            host_id,
            host_name=host.name,
            custom_task_id=task_id,
        )
        self._queue.put_nowait(job.id)
        return job

    async def _async_worker(self) -> None:
        while True:
            job_id = await self._queue.get()
            try:
                await self._async_run(job_id)
            finally:
                self._queue.task_done()

    async def _async_run(self, job_id: UUID) -> None:
        job = await self._repository.async_get(job_id)
        if job is None or job.host_id is None:
            return
        host = await self._hosts.async_get(job.host_id)
        if host is None:
            await self._finish_failure(job, None, "host_not_found", "")
            return
        if not await self._repository.async_claim(job_id):
            return
        lock = self._host_locks.setdefault(host.id, asyncio.Lock())
        try:
            if job.action is JobAction.CUSTOM_TASK:
                if job.custom_task_id is None:
                    await self._finish_failure(job, host, "custom_task_not_found", "")
                    return
                custom_task = await self._custom_tasks.async_get(job.custom_task_id)
                if custom_task is None:
                    await self._finish_failure(job, host, "custom_task_not_found", "")
                    return
                async with lock:
                    result = await self._executor.async_execute_custom(
                        custom_task, host
                    )
            elif job.action in _MUTATING_ACTIONS:
                async with lock:
                    result = await self._executor.async_execute(job.action, host)
            else:
                result = await self._executor.async_execute(job.action, host)
            await self._finish_success(job, host, result)
        except AutomationExecutionError as err:
            await self._finish_failure(
                job, host, err.code, err.output, exit_code=err.exit_code
            )
        except Exception:
            await self._finish_failure(job, host, "internal_execution_error", "")

    async def _finish_success(
        self, job: Job, host: Host, result: ExecutionResult
    ) -> None:
        if result.snapshot is not None:
            snapshot = result.snapshot
            await self._hosts.async_update_status(
                host.id,
                distribution=snapshot.distribution,
                distribution_version=snapshot.distribution_version,
                kernel=snapshot.kernel,
                updates=snapshot.updates,
                security_updates=snapshot.security_updates,
                reboot_required=snapshot.reboot_required,
                status=snapshot.status,
                checked_at=snapshot.checked_at,
            )
        output, truncated = _safe_output(result.output, host)
        await self._repository.async_finish(
            job.id,
            state=JobState.SUCCESS,
            output=output,
            truncated=truncated,
            exit_code=result.exit_code,
            reboot_required=result.reboot_required,
        )

    async def _finish_failure(
        self,
        job: Job,
        host: Host | None,
        code: str,
        raw_output: str,
        *,
        exit_code: int | None = None,
    ) -> None:
        output, truncated = _safe_output(raw_output, host)
        await self._repository.async_finish(
            job.id,
            state=JobState.FAILED,
            output=output,
            truncated=truncated,
            exit_code=exit_code,
            error_code=code,
        )


def _safe_output(output: str, host: Host | None) -> tuple[str, bool]:
    """Redact connection data and truncate by encoded byte length."""
    redacted = output.replace("\x00", "")
    if host is not None:
        for sensitive in (host.address, host.username):
            redacted = redacted.replace(sensitive, "[redacted]")
    encoded = redacted.encode("utf-8")
    if len(encoded) <= MAX_JOB_LOG_BYTES:
        return redacted, False
    return encoded[:MAX_JOB_LOG_BYTES].decode("utf-8", errors="ignore"), True


def _job_from_row(row: sqlite3.Row) -> Job:
    return Job(
        id=UUID(row["id"]),
        action=JobAction(row["action"]),
        host_id=UUID(row["host_id"]) if row["host_id"] is not None else None,
        host_name=row["host_name"],
        custom_task_id=(
            UUID(row["custom_task_id"]) if row["custom_task_id"] is not None else None
        ),
        state=JobState(row["state"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        started_at=(
            datetime.fromisoformat(row["started_at"])
            if row["started_at"] is not None
            else None
        ),
        finished_at=(
            datetime.fromisoformat(row["finished_at"])
            if row["finished_at"] is not None
            else None
        ),
        exit_code=row["exit_code"],
        error_code=row["error_code"],
        log_available=bool(row["log_available"]),
        reboot_required=(
            bool(row["reboot_required"]) if row["reboot_required"] is not None else None
        ),
    )
