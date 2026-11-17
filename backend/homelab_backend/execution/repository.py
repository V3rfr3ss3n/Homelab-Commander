"""SQLite job adapter: immutable scopes, history and transactional recovery."""

import json
import sqlite3
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from ..contracts.capabilities import RecoveryMode
from ..contracts.resources import ResourceKind, ResourceRef
from ..database import Database
from ..models import Job, JobAction, JobLog, JobState
from ..policy.application import PolicyGuard
from ..policy.domain import Permission
from ..policy.store import policy_for
from .scope import ExecutionContext, JobExecution, OperationScope
from .targets import connection_revision, resolve_target

DEFAULT_CONTEXT = ExecutionContext()
JOB_TIME = "COALESCE(jobs.finished_at,jobs.started_at,jobs.created_at)"
JOB_TIMESTAMP = f"hlc_timestamp({JOB_TIME})"
NEEDS_REVIEW = (
    "(jobs.state='failed' AND jobs.reviewed_at IS NULL "
    "AND (jobs.error_code IS 'execution_interrupted' OR NOT EXISTS(SELECT 1 "
    "FROM jobs later WHERE later.state='success' "
    "AND later.host_id IS jobs.host_id AND later.action=jobs.action "
    "AND json_extract(later.execution_json, '$.scope.target.id') "
    "IS json_extract(jobs.execution_json, '$.scope.target.id') "
    "AND json_extract(later.execution_json, '$.scope.operation') "
    "IS json_extract(jobs.execution_json, '$.scope.operation') "
    "AND later.custom_task_id IS jobs.custom_task_id "
    "AND later.package_name IS jobs.package_name "
    "AND later.package_names_json = jobs.package_names_json "
    "AND later.created_at>jobs.created_at)))"
)
JobSort = Literal["newest", "oldest", "host", "action", "state"]

_SELECT = (
    "SELECT jobs.id, jobs.action, jobs.host_id, hosts.name AS host_name, jobs.state, "
    "jobs.created_at, jobs.started_at, jobs.finished_at, jobs.exit_code, "
    "jobs.error_code, jobs.reboot_required, jobs.custom_task_id, "
    "jobs.package_name, jobs.package_names_json, "
    "jobs.reviewed_at, jobs.execution_json, jobs.interrupted_at, "
    "jobs.interrupted_started_at, jobs.recovery_count, "
    f"{NEEDS_REVIEW} AS needs_review, "
    "EXISTS(SELECT 1 FROM job_logs WHERE job_logs.job_id = jobs.id) "
    "AS log_available FROM jobs LEFT JOIN hosts ON hosts.id = jobs.host_id"
)


class JobRepository:
    """Persist queue state and bounded output independently of workers."""

    def __init__(
        self, database: Database, *, policy: PolicyGuard | None = None
    ) -> None:
        self._database = database
        self._policy = policy or policy_for(database)

    async def async_create(
        self,
        action: JobAction,
        host_id: UUID | None,
        *,
        host_name: str | None = None,
        custom_task_id: UUID | None = None,
        package_name: str | None = None,
        package_names: tuple[str, ...] = (),
        context: ExecutionContext = DEFAULT_CONTEXT,
        target: ResourceRef | None = None,
        operation: str | None = None,
        recovery: RecoveryMode = RecoveryMode.NEVER_REPLAY,
    ) -> Job:
        now = datetime.now(UTC)
        package_names = tuple(sorted(package_names))
        target = target or (
            ResourceRef(ResourceKind.HOST, host_id) if host_id else None
        )
        if target is None or (
            context.approval_id is not None and context.principal is None
        ):
            raise ValueError("Target required; approvals need an authenticated context")
        if action is not JobAction.RESOURCE_OPERATION:
            if (
                host_id is None
                or target != ResourceRef(ResourceKind.HOST, host_id)
                or operation is not None
            ):
                raise ValueError("Legacy action requires its exact Host target")
            operation = f"linux.{action}"
            recovery = (
                RecoveryMode.RETRY_READ
                if action in {JobAction.TEST_CONNECTION, JobAction.CHECK_UPDATES}
                else RecoveryMode.NEVER_REPLAY
            )
        elif operation is None or custom_task_id or package_name or package_names:
            raise ValueError(
                "Generic operation requires a typed operation without legacy parameters"
            )
        job_id = uuid4()

        def create(connection: sqlite3.Connection) -> Job:
            execution_host, conflicts = resolve_target(connection, target)
            task = (
                connection.execute(
                    "SELECT updated_at FROM custom_tasks WHERE id=?",
                    (str(custom_task_id),),
                ).fetchone()
                if custom_task_id
                else None
            )
            execution = JobExecution(
                scope=OperationScope(
                    target=target,
                    operation=operation,
                    execution_host_id=execution_host,
                    conflicts=conflicts,
                    recovery=recovery,
                    package_name=package_name,
                    package_names=package_names,
                    custom_task_id=custom_task_id,
                    task_revision=task["updated_at"] if task else None,
                    connection_revision=connection_revision(connection, execution_host),
                ),
                context=context,
            )
            job = Job(
                id=job_id,
                action=action,
                host_id=execution_host,
                host_name=host_name,
                custom_task_id=custom_task_id,
                package_name=package_name,
                package_names=package_names,
                state=JobState.QUEUED,
                created_at=now,
                execution=execution,
            )
            connection.execute(
                "INSERT INTO jobs (id,action,host_id,custom_task_id,package_name,"
                "package_names_json,state,created_at,execution_json) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    str(job.id),
                    action,
                    str(execution_host) if execution_host else None,
                    str(custom_task_id) if custom_task_id else None,
                    package_name,
                    json.dumps(package_names),
                    job.state,
                    now.isoformat(),
                    execution.model_dump_json(),
                ),
            )
            return job

        return await self._database.async_transaction(create)

    async def async_prepare_resource(
        self, target: ResourceRef, operation: str
    ) -> OperationScope:
        def prepare(connection: sqlite3.Connection) -> OperationScope:
            host_id, conflicts = resolve_target(connection, target)
            return OperationScope(
                target=target,
                operation=operation,
                execution_host_id=host_id,
                conflicts=conflicts,
                connection_revision=connection_revision(connection, host_id),
            )

        return await self._database.async_transaction(prepare)

    async def async_scope_current(self, execution: JobExecution) -> bool:
        def current(connection: sqlite3.Connection) -> bool:
            scope = execution.scope
            try:
                host_id, conflicts = resolve_target(connection, scope.target)
                if (host_id, conflicts) != (scope.execution_host_id, scope.conflicts):
                    return False
                if (
                    scope.connection_revision is not None
                    and connection_revision(connection, host_id)
                    != scope.connection_revision
                ):
                    return False
                if scope.task_revision is not None:
                    task = connection.execute(
                        "SELECT updated_at FROM custom_tasks WHERE id=?",
                        (str(scope.custom_task_id),),
                    ).fetchone()
                    if task is None or task["updated_at"] != scope.task_revision:
                        return False
            except ValueError:
                return False
            return True

        return await self._database.async_transaction(current)

    async def async_get(self, job_id: UUID) -> Job | None:
        row = await self._database.async_fetch_one(
            f"{_SELECT} WHERE jobs.id = ?", (str(job_id),)
        )
        return _job_from_row(row) if row is not None else None

    async def async_list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        host_id: UUID | None = None,
        state: JobState | None = None,
        completed: bool = False,
        start: datetime | None = None,
        end: datetime | None = None,
        action: JobAction | None = None,
        sort: JobSort | None = None,
    ) -> tuple[Job, ...]:
        clause, parameters = job_filter(host_id, state, completed, start, end, action)
        order = "jobs.finished_at DESC" if completed else "jobs.created_at DESC"
        if sort is not None:
            order = {
                "newest": f"{JOB_TIMESTAMP} DESC",
                "oldest": f"{JOB_TIMESTAMP} ASC",
                "host": f"hosts.name COLLATE NOCASE ASC, {JOB_TIMESTAMP} DESC",
                "action": f"jobs.action ASC, {JOB_TIMESTAMP} DESC",
                "state": f"jobs.state ASC, {JOB_TIMESTAMP} DESC",
            }[sort]
        rows = await self._database.async_fetch_all(
            f"{_SELECT}{clause} ORDER BY {order}, jobs.id DESC LIMIT ? OFFSET ?",
            (*parameters, limit, offset),
        )
        return tuple(_job_from_row(row) for row in rows)

    async def async_count(
        self,
        *,
        host_id: UUID | None = None,
        state: JobState | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        action: JobAction | None = None,
    ) -> int:
        clause, parameters = job_filter(host_id, state, False, start, end, action)
        row = await self._database.async_fetch_one(
            f"SELECT COUNT(*) AS count FROM jobs{clause}", parameters
        )
        return row["count"] if row is not None else 0

    async def async_unresolved_failure(self) -> Job | None:
        row = await self._database.async_fetch_one(
            f"SELECT jobs.id FROM jobs WHERE {NEEDS_REVIEW} "
            "ORDER BY jobs.created_at DESC LIMIT 1"
        )
        return await self.async_get(UUID(row["id"])) if row else None

    async def async_review(self, job_id: UUID) -> Job:
        """Acknowledge one failed job without changing its outcome or log."""
        await self._policy.async_require(Permission.REVIEW_JOB)
        await self._database.async_execute(
            "UPDATE jobs SET reviewed_at = COALESCE(reviewed_at, ?) "
            "WHERE id = ? AND state = 'failed'",
            (datetime.now(UTC).isoformat(), str(job_id)),
        )
        job = await self.async_get(job_id)
        if job is None:
            raise KeyError("Job not found")
        if job.state != JobState.FAILED:
            raise ValueError("Only failed jobs can be marked as reviewed")
        return job

    async def async_recover_queued(self) -> tuple[UUID, ...]:
        """Resume unstarted work; never replay uncertain remote mutations."""

        def recover(connection: sqlite3.Connection) -> tuple[UUID, ...]:
            now = datetime.now(UTC).isoformat()
            for row in connection.execute(
                "SELECT id,action,execution_json FROM jobs WHERE state='running'"
            ).fetchall():
                retry = row["action"] in {
                    JobAction.TEST_CONNECTION,
                    JobAction.CHECK_UPDATES,
                }
                # Generic work is never replayed by the legacy startup path.
                if retry:
                    connection.execute(
                        "UPDATE jobs SET state='queued',"
                        "interrupted_started_at=started_at,started_at=NULL,"
                        "interrupted_at=?,"
                        "recovery_count=recovery_count+1 WHERE id=?",
                        (now, row["id"]),
                    )
                else:
                    connection.execute(
                        "UPDATE jobs SET state='failed',finished_at=?,interrupted_at=?,"
                        "interrupted_started_at=started_at,"
                        "error_code='execution_interrupted',"
                        "recovery_count=recovery_count+1 "
                        "WHERE id=?",
                        (now, now, row["id"]),
                    )
                    connection.execute(
                        "INSERT INTO job_logs(job_id,output,truncated) VALUES(?,?,0) "
                        "ON CONFLICT(job_id) DO NOTHING",
                        (
                            row["id"],
                            (
                                "Execution interrupted. Remote effects are uncertain. "
                                "Inspect the resource before starting new work."
                            ),
                        ),
                    )
            return tuple(
                UUID(row["id"])
                for row in connection.execute(
                    "SELECT id FROM jobs WHERE state='queued' ORDER BY created_at,id"
                )
            )

        return await self._database.async_transaction(recover)

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


def _job_from_row(row: sqlite3.Row) -> Job:
    return Job(
        id=UUID(row["id"]),
        action=JobAction(row["action"]),
        host_id=UUID(row["host_id"]) if row["host_id"] is not None else None,
        host_name=row["host_name"],
        custom_task_id=(
            UUID(row["custom_task_id"]) if row["custom_task_id"] is not None else None
        ),
        package_name=row["package_name"],
        package_names=tuple(json.loads(row["package_names_json"])),
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
        needs_review=bool(row["needs_review"]),
        reviewed_at=(
            datetime.fromisoformat(row["reviewed_at"])
            if row["reviewed_at"] is not None
            else None
        ),
        execution=JobExecution.model_validate_json(row["execution_json"])
        if row["execution_json"]
        else None,
        interrupted_at=datetime.fromisoformat(row["interrupted_at"])
        if row["interrupted_at"]
        else None,
        interrupted_started_at=(
            datetime.fromisoformat(row["interrupted_started_at"])
            if row["interrupted_started_at"]
            else None
        ),
        recovery_count=row["recovery_count"],
        reboot_required=(
            bool(row["reboot_required"]) if row["reboot_required"] is not None else None
        ),
    )


def job_filter(
    host_id: UUID | None,
    state: JobState | None,
    completed: bool,
    start: datetime | None = None,
    end: datetime | None = None,
    action: JobAction | None = None,
) -> tuple[str, tuple[object, ...]]:
    clauses: list[str] = []
    parameters: list[object] = []
    if host_id is not None:
        clauses.append("jobs.host_id = ?")
        parameters.append(str(host_id))
    if state is not None:
        clauses.append("jobs.state = ?")
        parameters.append(state)
    if action is not None:
        clauses.append("jobs.action = ?")
        parameters.append(action)
    if start is not None:
        clauses.append(f"{JOB_TIMESTAMP} >= ?")
        parameters.append(start.timestamp())
    if end is not None:
        clauses.append(f"{JOB_TIMESTAMP} < ?")
        parameters.append(end.timestamp())
    if completed:
        clauses.append("jobs.finished_at IS NOT NULL")
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), tuple(parameters)
