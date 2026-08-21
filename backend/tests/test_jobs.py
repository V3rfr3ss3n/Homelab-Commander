"""Job serialization and package-provider unit tests."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from backend.homelab_backend.automation import ExecutionResult
from backend.homelab_backend.custom_tasks import CustomTaskRepository
from backend.homelab_backend.database import Database
from backend.homelab_backend.hosts import HostRepository
from backend.homelab_backend.jobs import (
    MAX_JOB_LOG_BYTES,
    JobManager,
    JobRepository,
    _safe_output,
)
from backend.homelab_backend.models import (
    CustomTask,
    CustomTaskCreate,
    CustomTaskMode,
    Host,
    HostCreate,
    JobAction,
    JobState,
)
from backend.homelab_backend.package_providers import (
    DebianAptProvider,
    package_provider,
)


class BlockingExecutor:
    """Observe concurrency without running external commands."""

    def __init__(self) -> None:
        self.first_started = asyncio.Event()
        self.release_first = asyncio.Event()
        self.both_finished = asyncio.Event()
        self.calls = 0
        self.active = 0
        self.maximum_active = 0

    async def async_execute(self, _action: JobAction, _host: Host) -> ExecutionResult:
        self.calls += 1
        call = self.calls
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        if call == 1:
            self.first_started.set()
            await self.release_first.wait()
        self.active -= 1
        if call == 2:
            self.both_finished.set()
        return ExecutionResult(output="synthetic")

    async def async_execute_custom(
        self, _task: CustomTask, _host: Host
    ) -> ExecutionResult:
        return ExecutionResult(output="synthetic custom")


class ExplodingExecutor(BlockingExecutor):
    """Exercise the defensive unknown-exception boundary."""

    async def async_execute(self, _action: JobAction, _host: Host) -> ExecutionResult:
        raise RuntimeError("synthetic internal detail")


async def test_mutating_jobs_are_serialized_per_host(tmp_path: Path) -> None:
    """Multiple workers cannot update the same host concurrently."""
    database = Database(tmp_path / "jobs.db")
    await database.async_migrate()
    hosts = HostRepository(database)
    host = await hosts.async_create(
        HostCreate(
            name="Node 01",
            address="node-01.example.invalid",
            username="automation",
        )
    )
    repository = JobRepository(database)
    executor = BlockingExecutor()
    manager = JobManager(
        repository,
        hosts,
        CustomTaskRepository(database, allow_shell=False),
        executor,
        worker_count=2,
    )
    await manager.async_start()
    try:
        first = await manager.async_enqueue(JobAction.UPDATE, host.id)
        second = await manager.async_enqueue(JobAction.UPDATE, host.id)
        await executor.first_started.wait()
        await asyncio.sleep(0)
        assert executor.calls == 1
        executor.release_first.set()
        await executor.both_finished.wait()
        await manager.async_wait_idle()
        assert executor.maximum_active == 1
        assert (await repository.async_get(first.id)).state is JobState.SUCCESS  # type: ignore[union-attr]
        assert (await repository.async_get(second.id)).state is JobState.SUCCESS  # type: ignore[union-attr]
    finally:
        await manager.async_stop()


def test_debian_apt_provider_parses_updates_and_never_requests_reboot() -> None:
    """APT normalization counts package rows and security sources."""
    provider = DebianAptProvider()
    status = provider.parse_updates(
        "Listing...\n"
        "package-a/stable 2.0 amd64 [upgradable from: 1.0]\n"
        "package-b/stable-security 3.0 amd64 [upgradable from: 2.0]\n",
        reboot_required=True,
    )
    assert status.updates == 2
    assert status.security_updates == 1
    assert status.reboot_required
    assert provider.update_module == (
        "ansible.builtin.apt",
        "update_cache=true upgrade=dist",
    )


def test_unknown_package_provider_fails_closed() -> None:
    """Unsupported package managers are never guessed."""
    with pytest.raises(ValueError, match="unsupported"):
        package_provider("unknown")


def test_job_manager_rejects_unsafe_worker_counts() -> None:
    """Concurrency stays inside the documented bounded range."""
    with pytest.raises(ValueError, match="between 1 and 16"):
        JobManager(None, None, None, BlockingExecutor(), worker_count=0)  # type: ignore[arg-type]


async def test_recovered_job_is_requeued_and_completed(tmp_path: Path) -> None:
    """A queued job survives a worker restart and is processed exactly once."""
    database = Database(tmp_path / "recovery.db")
    await database.async_migrate()
    hosts = HostRepository(database)
    host = await hosts.async_create(
        HostCreate(
            name="Node 01",
            address="node-01.example.invalid",
            username="automation",
        )
    )
    repository = JobRepository(database)
    queued = await repository.async_create(JobAction.CHECK_UPDATES, host.id)
    executor = BlockingExecutor()
    executor.release_first.set()
    manager = JobManager(
        repository,
        hosts,
        CustomTaskRepository(database, allow_shell=False),
        executor,
        worker_count=1,
    )
    await manager.async_start()
    try:
        await manager.async_wait_idle()
        persisted = await repository.async_get(queued.id)
        assert persisted is not None
        assert persisted.state is JobState.SUCCESS
    finally:
        await manager.async_stop()


async def test_job_manager_handles_stale_identities_and_claims(tmp_path: Path) -> None:
    """Recovered inconsistencies fail closed without executing another target."""
    database = Database(tmp_path / "stale.db")
    await database.async_migrate()
    hosts = HostRepository(database)
    tasks = CustomTaskRepository(database, allow_shell=False)
    repository = JobRepository(database)
    manager = JobManager(repository, hosts, tasks, BlockingExecutor())

    with pytest.raises(KeyError, match="Host"):
        await manager.async_enqueue_custom(uuid4(), uuid4())
    await manager._async_run(uuid4())

    removed_host = await hosts.async_create(
        HostCreate(
            name="Removed",
            address="removed.example.invalid",
            username="automation",
        )
    )
    orphan = await repository.async_create(JobAction.UPDATE, removed_host.id)
    await hosts.async_delete(removed_host.id)
    await manager._async_run(orphan.id)
    assert (await repository.async_get(orphan.id)).state is JobState.QUEUED  # type: ignore[union-attr]

    missing_lookup_host = await hosts.async_create(
        HostCreate(
            name="Missing lookup",
            address="missing.example.invalid",
            username="automation",
        )
    )
    missing_lookup = await repository.async_create(
        JobAction.UPDATE, missing_lookup_host.id
    )
    with patch.object(hosts, "async_get", AsyncMock(return_value=None)):
        await manager._async_run(missing_lookup.id)
    assert (
        await repository.async_get(missing_lookup.id)
    ).error_code == "host_not_found"  # type: ignore[union-attr]

    host = await hosts.async_create(
        HostCreate(
            name="Node 01",
            address="node-01.example.invalid",
            username="automation",
        )
    )
    already_claimed = await repository.async_create(JobAction.UPDATE, host.id)
    assert await repository.async_claim(already_claimed.id)
    await manager._async_run(already_claimed.id)
    assert (await repository.async_get(already_claimed.id)).state is JobState.RUNNING  # type: ignore[union-attr]

    no_identity = await repository.async_create(JobAction.CUSTOM_TASK, host.id)
    await manager._async_run(no_identity.id)
    assert (
        await repository.async_get(no_identity.id)
    ).error_code == "custom_task_not_found"  # type: ignore[union-attr]

    removed_task = await tasks.async_create(
        CustomTaskCreate(name="Removed task", argv=("true",))
    )
    missing_task = await repository.async_create(
        JobAction.CUSTOM_TASK, host.id, custom_task_id=removed_task.id
    )
    with patch.object(tasks, "async_get", AsyncMock(return_value=None)):
        await manager._async_run(missing_task.id)
    assert (
        await repository.async_get(missing_task.id)
    ).error_code == "custom_task_not_found"  # type: ignore[union-attr]


async def test_job_manager_sanitizes_unknown_failures_and_large_output(
    tmp_path: Path,
) -> None:
    """Unexpected errors expose only a stable code and logs remain byte bounded."""
    database = Database(tmp_path / "failure.db")
    await database.async_migrate()
    hosts = HostRepository(database)
    host = await hosts.async_create(
        HostCreate(
            name="Node 01",
            address="node-01.example.invalid",
            username="automation",
        )
    )
    repository = JobRepository(database)
    manager = JobManager(
        repository,
        hosts,
        CustomTaskRepository(database, allow_shell=False),
        ExplodingExecutor(),
    )
    job = await repository.async_create(JobAction.CHECK_UPDATES, host.id)
    await manager._async_run(job.id)
    persisted = await repository.async_get(job.id)
    assert persisted is not None
    assert persisted.error_code == "internal_execution_error"
    assert await repository.async_log(job.id) is not None

    assert _safe_output("synthetic\x00", None) == ("synthetic", False)
    output, truncated = _safe_output("å" * MAX_JOB_LOG_BYTES, host)
    assert truncated
    assert len(output.encode()) <= MAX_JOB_LOG_BYTES


def test_custom_task_validation_rejects_unsafe_arguments_and_shells() -> None:
    """Both execution representations validate their own unsafe edge cases."""
    with pytest.raises(ValueError, match="arguments"):
        CustomTaskCreate(name="Too many", argv=("x",) * 65)
    with pytest.raises(ValueError, match="Shell tasks"):
        CustomTaskCreate(
            name="Invalid shell", mode=CustomTaskMode.SHELL, shell_command=""
        )
