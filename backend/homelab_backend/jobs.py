"""Persistent asynchronous worker with deterministic resource conflicts."""

import asyncio
from contextlib import suppress
from typing import Protocol
from uuid import UUID

from .automation import AutomationExecutionError, AutomationExecutor, ExecutionResult
from .contracts.resources import ResourceKind, ResourceRef
from .custom_tasks import CustomTaskRepository
from .execution.authorization import JobAuthorization, legacy_principal
from .execution.locks import ResourceLocks
from .execution.repository import (
    DEFAULT_CONTEXT,
)
from .execution.repository import (
    JOB_TIMESTAMP as JOB_TIMESTAMP,
)
from .execution.repository import (
    NEEDS_REVIEW as NEEDS_REVIEW,
)
from .execution.repository import (
    JobRepository as JobRepository,
)
from .execution.repository import (
    JobSort as JobSort,
)
from .execution.repository import (
    job_filter as job_filter,
)
from .execution.scope import ExecutionContext, JobExecution, OperationScope
from .failure_logging import log_internal_failure
from .hosts import HostRepository
from .models import Host, Job, JobAction, JobState
from .policy.application import AuthorizationDenied, PolicyGuard, principal_scope
from .policy.approvals import ApprovalService
from .policy.domain import Permission
from .policy.store import policy_for
from .task_compatibility import TaskCompatibilityService

MAX_JOB_LOG_BYTES = 64 * 1024


class ResourceOperation(Protocol):
    """Statically injected feature port; production installs none until #46.

    Authorization is mandatory at enqueue and immediately before execution.
    Metadata, capability readiness and approval references confer no permission.
    """

    operation: str
    kind: ResourceKind

    async def async_authorize(
        self, scope: OperationScope, context: ExecutionContext
    ) -> bool:
        """Revalidate policy/identity; missing or unknown authority returns False."""

    async def async_execute(self, scope: OperationScope) -> ExecutionResult:
        """Execute the exact typed scope; never add implicit reboot or parameters."""


class JobManager:
    """Run persistent jobs with bounded workers and canonical resource conflicts."""

    def __init__(
        self,
        repository: JobRepository,
        hosts: HostRepository,
        custom_tasks: CustomTaskRepository,
        executor: AutomationExecutor,
        *,
        worker_count: int = 2,
        compatibility: TaskCompatibilityService | None = None,
        operations: tuple[ResourceOperation, ...] = (),
        policy: PolicyGuard | None = None,
        approvals: ApprovalService | None = None,
    ) -> None:
        if worker_count < 1 or worker_count > 16:
            raise ValueError("worker_count must be between 1 and 16")
        self._compatibility = compatibility or TaskCompatibilityService(
            repository._database, custom_tasks, hosts, executor
        )
        self._authorization = JobAuthorization(
            policy or policy_for(repository._database), approvals
        )
        self._repository = repository
        self._hosts = hosts
        self._custom_tasks = custom_tasks
        self._executor = executor
        self._worker_count = worker_count
        self._queue: asyncio.Queue[UUID] = asyncio.Queue()
        self._workers: list[asyncio.Task[None]] = []
        self._locks = ResourceLocks()
        self._operations = {(item.kind, item.operation): item for item in operations}
        if len(self._operations) != len(operations):
            raise ValueError("Duplicate resource operation binding")

    async def async_start(self) -> None:
        """Recover persistent work and start bounded workers."""
        if self._workers:
            raise RuntimeError("Job manager is already started")
        self._queue = asyncio.Queue()
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

    async def async_enqueue(
        self,
        action: JobAction,
        host_id: UUID,
        package_name: str | None = None,
        package_names: tuple[str, ...] = (),
        *,
        context: ExecutionContext = DEFAULT_CONTEXT,
    ) -> Job:
        """Validate the exact target before creating persistent work."""
        if action in {JobAction.CUSTOM_TASK, JobAction.RESOURCE_OPERATION}:
            raise ValueError("Use the dedicated operation entrance")
        context = self._authorization.capture(context)
        await self._authorization.guard.async_require(
            Permission.EXECUTE,
            ResourceRef(ResourceKind.HOST, host_id),
            principal=context.principal,
            operation=f"linux.{action}",
        )
        if context.approval_id is not None:
            await self._authorization.guard.async_deny(
                Permission.EXECUTE,
                ResourceRef(ResourceKind.HOST, host_id),
                context.principal or legacy_principal(context.caller),
                "approval_unexpected",
            )
        host = await self._hosts.async_get(host_id)
        if host is None:
            raise KeyError("Host not found")
        job = await self._repository.async_create(
            action,
            host_id,
            host_name=host.name,
            package_name=package_name,
            package_names=package_names,
            context=context,
        )
        self._queue.put_nowait(job.id)
        return job

    async def async_wait_idle(self) -> None:
        """Wait until all currently queued work has reached persistence."""
        await self._queue.join()

    async def async_enqueue_custom(
        self,
        task_id: UUID,
        host_id: UUID,
        *,
        context: ExecutionContext = DEFAULT_CONTEXT,
    ) -> Job:
        """Queue one enabled custom task with two validated identities."""
        context = self._authorization.capture(context)
        await self._authorization.guard.async_require(
            Permission.EXECUTE,
            ResourceRef(ResourceKind.HOST, host_id),
            principal=context.principal,
            operation="linux.custom_task",
        )
        if context.approval_id is not None:
            await self._authorization.guard.async_deny(
                Permission.EXECUTE,
                ResourceRef(ResourceKind.HOST, host_id),
                context.principal or legacy_principal(context.caller),
                "approval_unexpected",
            )
        host = await self._hosts.async_get(host_id)
        if host is None:
            raise KeyError("Host not found")
        task = await self._custom_tasks.async_get(task_id)
        if task is None:
            raise KeyError("Custom task not found")
        if not task.enabled:
            raise ValueError("Custom task is disabled")
        permitted_task, _ = await self._compatibility.async_require(task_id, host_id)
        job = await self._repository.async_create(
            JobAction.CUSTOM_TASK,
            host_id,
            host_name=host.name,
            custom_task_id=task_id,
            context=context,
        )
        if (
            job.execution is None
            or job.execution.scope.task_revision
            != permitted_task.updated_at.isoformat()
        ):
            await self._finish_failure(job, host, "execution_scope_changed", "")
            raise ValueError("Task changed while queueing")
        self._queue.put_nowait(job.id)
        return job

    async def async_enqueue_resource(
        self, target: ResourceRef, operation: str, *, context: ExecutionContext
    ) -> Job:
        """Internal feature entrance, default-denied and not exposed over HTTP."""
        handler = self._operations.get((target.kind, operation))
        if handler is None:
            raise ValueError("Resource operation is not permitted")

        context = self._authorization.capture(context)
        scope = await self._repository.async_prepare_resource(target, operation)
        await self._authorization.async_authorize(
            JobExecution(scope=scope, context=context)
        )
        if not await handler.async_authorize(scope, context):
            raise ValueError("Resource operation is not permitted")
        job = await self._repository.async_create(
            JobAction.RESOURCE_OPERATION,
            scope.execution_host_id,
            target=target,
            operation=operation,
            context=context,
        )
        # Do not broaden a target after authorization if its association changed.
        if job.execution is None or job.execution.scope != scope:
            await self._finish_failure(job, None, "execution_scope_changed", "")
            raise ValueError("Execution target changed while queueing")
        self._queue.put_nowait(job.id)
        return job

    async def _async_worker(self) -> None:
        while True:
            job_id = await self._queue.get()
            try:
                await self._async_run(job_id)
            except Exception as error:
                log_internal_failure(error, str(job_id), "execute_job")
                await self._repository.async_finish(
                    job_id,
                    state=JobState.FAILED,
                    output=f"Internal execution failure. Reference: {job_id}",
                    truncated=False,
                    error_code="internal_execution_error",
                )
            finally:
                self._queue.task_done()

    async def _async_run(self, job_id: UUID) -> None:
        job = await self._repository.async_get(job_id)
        if job is None or job.state is not JobState.QUEUED:
            return
        if job.execution is None:
            await self._finish_failure(job, None, "host_not_found", "")
            return
        actor = job.execution.context.principal or legacy_principal(
            job.execution.context.caller
        )
        with principal_scope(actor):
            await self._async_run_authorized(job)

    async def _async_run_authorized(self, job: Job) -> None:
        job_id = job.id
        assert job.execution is not None
        # Waiting jobs remain queued. Claim only after all conflicts are held.
        async with self._locks.hold(job.execution.scope.conflicts):
            if not await self._repository.async_claim(job_id):
                return
            host = await self._hosts.async_get(job.host_id) if job.host_id else None
            try:
                await self._authorization.async_authorize(job.execution)
                if job.action is not JobAction.RESOURCE_OPERATION and host is None:
                    await self._finish_failure(job, None, "host_not_found", "")
                    return
                if not await self._repository.async_scope_current(job.execution):
                    await self._finish_failure(job, host, "execution_scope_changed", "")
                    return
                if job.action is JobAction.RESOURCE_OPERATION:
                    await self._run_resource(job, host)
                    return
                assert host is not None
                scope = job.execution.scope
                if (
                    scope.operation != f"linux.{job.action}"
                    or scope.package_name != job.package_name
                    or scope.package_names != job.package_names
                    or scope.custom_task_id != job.custom_task_id
                ):
                    await self._finish_failure(job, host, "execution_scope_changed", "")
                    return
                if job.action is JobAction.CUSTOM_TASK:
                    if (
                        job.custom_task_id is None
                        or await self._custom_tasks.async_get(job.custom_task_id)
                        is None
                    ):
                        await self._finish_failure(
                            job, host, "custom_task_not_found", ""
                        )
                        return
                    try:
                        custom_task, host = await self._compatibility.async_require(
                            job.custom_task_id, host.id, fresh=True
                        )
                    except KeyError, ValueError:
                        await self._finish_failure(
                            job, host, "custom_task_not_permitted", ""
                        )
                        return
                    if not await self._repository.async_scope_current(job.execution):
                        await self._finish_failure(
                            job, host, "execution_scope_changed", ""
                        )
                        return
                    await self._authorization.async_authorize(
                        job.execution, job_id=job.id
                    )
                    result = await self._executor.async_execute_custom(
                        custom_task, host
                    )
                else:
                    await self._authorization.async_authorize(
                        job.execution, job_id=job.id
                    )
                    result = await self._execute_builtin(job, host)
                await self._finish_success(job, host, result)
            except AuthorizationDenied:
                await self._finish_failure(
                    job,
                    host,
                    "policy_denied",
                    "This action is not permitted by backend policy.",
                )
            except AutomationExecutionError as err:
                await self._finish_failure(
                    job,
                    host,
                    "resource_operation_failed"
                    if job.action is JobAction.RESOURCE_OPERATION
                    else err.code,
                    "Resource operation failed."
                    if job.action is JobAction.RESOURCE_OPERATION
                    else err.output,
                    exit_code=err.exit_code,
                )
            except Exception as error:
                log_internal_failure(error, str(job.id), "execute_job")
                await self._finish_failure(
                    job,
                    host,
                    "internal_execution_error",
                    f"Internal execution failure. Reference: {job.id}",
                )

    async def _run_resource(self, job: Job, host: Host | None) -> None:
        assert job.execution is not None
        scope = job.execution.scope
        handler = self._operations.get((scope.target.kind, scope.operation))
        if handler is None or not await handler.async_authorize(
            scope, job.execution.context
        ):
            await self._finish_failure(job, host, "operation_not_permitted", "")
            return
        if not await self._repository.async_scope_current(job.execution):
            await self._finish_failure(job, host, "execution_scope_changed", "")
            return
        await self._authorization.async_authorize(job.execution, job_id=job.id)
        result = await handler.async_execute(scope)
        if result.exit_code != 0:
            await self._finish_failure(
                job,
                host,
                "resource_operation_failed",
                "Resource operation failed.",
                exit_code=result.exit_code,
            )
            return
        # Feature output needs its own validated/redacted result contract before
        # exposure. Generic foundation exports only safe completion metadata.
        await self._repository.async_finish(
            job.id,
            state=JobState.SUCCESS,
            output="Resource operation completed.",
            truncated=False,
            exit_code=result.exit_code,
        )

    async def _execute_builtin(self, job: Job, host: Host) -> ExecutionResult:
        if job.package_names:
            return await self._executor.async_execute(
                job.action, host, package_names=job.package_names
            )
        if job.package_name is not None:
            return await self._executor.async_execute(
                job.action, host, job.package_name
            )
        return await self._executor.async_execute(job.action, host)

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
                packages=snapshot.packages,
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
