"""Synthetic contracts for resource job scopes, conflicts and safe recovery."""

import asyncio
import sqlite3
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from backend.homelab_backend.automation import AutomationExecutionError, ExecutionResult
from backend.homelab_backend.contracts.capabilities import RiskClass
from backend.homelab_backend.contracts.resources import (
    ProviderBinding,
    ResourceKind,
    ResourceRef,
)
from backend.homelab_backend.custom_tasks import CustomTaskRepository
from backend.homelab_backend.database import Database
from backend.homelab_backend.execution.locks import ResourceLocks
from backend.homelab_backend.execution.scope import (
    ExecutionContext,
    JobCaller,
    OperationScope,
)
from backend.homelab_backend.hosts import HostRepository
from backend.homelab_backend.jobs import JobManager, JobRepository
from backend.homelab_backend.models import (
    CustomTaskCreate,
    CustomTaskPatch,
    HostCreate,
    HostPatch,
    JobAction,
    JobState,
)
from backend.homelab_backend.policy.application import AuthorizationDenied, PolicyGuard
from backend.homelab_backend.policy.domain import OperationPolicy, PolicyEngine
from backend.homelab_backend.resources.application import ResourceRegistry
from backend.homelab_backend.resources.repository import SqliteResourceRepository
from backend.tests.test_jobs import BlockingExecutor


@pytest.mark.parametrize(
    "action", [JobAction.UPDATE, JobAction.REBOOT, JobAction.CUSTOM_TASK]
)
async def test_interrupted_mutations_are_never_requeued(
    tmp_path: Path, action: JobAction
) -> None:
    database = Database(tmp_path / "interrupted.db")
    await database.async_migrate()
    host = await HostRepository(database).async_create(
        HostCreate(
            name="Node 01", address="node-01.example.invalid", username="automation"
        )
    )
    jobs = JobRepository(database)
    interrupted = await jobs.async_create(action, host.id)
    assert await jobs.async_claim(interrupted.id)
    queued = await jobs.async_create(JobAction.UPDATE, host.id, package_name="vim")

    assert await jobs.async_recover_queued() == (queued.id,)
    recovered = await jobs.async_get(interrupted.id)
    assert recovered is not None
    assert recovered.state is JobState.FAILED
    assert recovered.error_code == "execution_interrupted"
    assert recovered.needs_review
    assert recovered.started_at is not None
    assert recovered.finished_at is not None


def synthetic_policy() -> PolicyGuard:
    return PolicyGuard(
        engine=PolicyEngine((
            OperationPolicy(
                "synthetic.service_update",
                frozenset({ResourceKind.MANAGED_SERVICE}),
                RiskClass.MUTATING,
            ),
        ))
    )


class SyntheticServiceOperation:
    """A statically injected test-only service operation, never a real provider."""

    operation = "synthetic.service_update"
    kind = ResourceKind.MANAGED_SERVICE

    def __init__(self) -> None:
        self.allowed = True
        self.executed: list[UUID] = []
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.release.set()
        self.error: Exception | None = None
        self.exit_code = 0

    async def async_authorize(
        self, scope: OperationScope, context: ExecutionContext
    ) -> bool:
        return self.allowed and context.caller is JobCaller.INTERNAL_ADMIN

    async def async_execute(self, scope: OperationScope) -> ExecutionResult:
        self.executed.append(scope.target.id)
        self.started.set()
        await self.release.wait()
        if self.error:
            raise self.error
        return ExecutionResult(
            output="synthetic unvalidated provider output", exit_code=self.exit_code
        )


async def workspace(tmp_path: Path):
    database = Database(tmp_path / "jobs.db")
    await database.async_migrate()
    hosts = HostRepository(database)
    host = await hosts.async_create(
        HostCreate(
            name="Node 01", address="node-01.example.invalid", username="automation"
        )
    )
    tasks = CustomTaskRepository(database, allow_shell=False)
    jobs = JobRepository(database)
    registry = ResourceRegistry(SqliteResourceRepository(database))
    service = await registry.async_create_service(
        "Service 01",
        "synthetic",
        ProviderBinding("synthetic.test", uuid4(), "demo_01"),
        host.id,
    )
    return database, hosts, host, tasks, jobs, registry, service


async def test_host_and_service_share_conflicts_while_unrelated_work_can_run(
    tmp_path: Path,
) -> None:
    _, hosts, host, tasks, jobs, registry, service = await workspace(tmp_path)
    other = await registry.async_create_service(
        "Service 02", "synthetic", ProviderBinding("synthetic.test", uuid4(), "demo_02")
    )
    executor = BlockingExecutor()
    operation = SyntheticServiceOperation()
    manager = JobManager(
        jobs,
        hosts,
        tasks,
        executor,
        worker_count=3,
        operations=(operation,),
        policy=synthetic_policy(),
    )
    await manager.async_start()
    try:
        update = await manager.async_enqueue(JobAction.UPDATE, host.id)
        await asyncio.wait_for(executor.first_started.wait(), 5)
        service_job = await manager.async_enqueue_resource(
            service.ref, operation.operation, context=ExecutionContext()
        )
        unrelated = await manager.async_enqueue_resource(
            other.ref, operation.operation, context=ExecutionContext()
        )
        await asyncio.wait_for(operation.started.wait(), 5)
        assert operation.executed == [other.id]
        assert (await jobs.async_get(service_job.id)).state is JobState.QUEUED
        executor.release_first.set()
        await asyncio.wait_for(manager.async_wait_idle(), 5)
        assert operation.executed == [other.id, service.id]
        for job in (update, service_job, unrelated):
            assert (await jobs.async_get(job.id)).state is JobState.SUCCESS
        log = await jobs.async_log(service_job.id)
        assert log.output == "Resource operation completed."
    finally:
        executor.release_first.set()
        await manager.async_stop()


async def test_generic_operation_is_default_denied_and_reauthorized(
    tmp_path: Path,
) -> None:
    _, hosts, host, tasks, jobs, _, service = await workspace(tmp_path)
    operation = SyntheticServiceOperation()
    manager = JobManager(
        jobs,
        hosts,
        tasks,
        BlockingExecutor(),
        operations=(operation,),
        policy=synthetic_policy(),
    )
    for target, name, context in (
        (service.ref, "synthetic.unknown", ExecutionContext()),
        (
            ResourceRef(ResourceKind.HOST, host.id),
            operation.operation,
            ExecutionContext(),
        ),
        (service.ref, operation.operation, ExecutionContext(approval_id=uuid4())),
        (
            service.ref,
            operation.operation,
            ExecutionContext(caller=JobCaller.EXTERNAL_ADMIN),
        ),
    ):
        with pytest.raises((ValueError, AuthorizationDenied), match="not permitted"):
            await manager.async_enqueue_resource(target, name, context=context)
    assert await jobs.async_count() == 0
    job = await manager.async_enqueue_resource(
        service.ref, operation.operation, context=ExecutionContext()
    )
    operation.allowed = False
    await manager._async_run(job.id)
    assert (await jobs.async_get(job.id)).error_code == "operation_not_permitted"
    assert not operation.executed
    with pytest.raises(ValueError, match="dedicated"):
        await manager.async_enqueue(JobAction.RESOURCE_OPERATION, host.id)
    with pytest.raises(ValueError, match="Duplicate"):
        JobManager(
            jobs, hosts, tasks, BlockingExecutor(), operations=(operation, operation)
        )


@pytest.mark.parametrize("change", ["relink", "delete", "connection", "task"])
async def test_dispatch_rejects_changed_snapshot(tmp_path: Path, change: str) -> None:
    _, hosts, host, tasks, jobs, registry, service = await workspace(tmp_path)
    operation = SyntheticServiceOperation()
    manager = JobManager(
        jobs,
        hosts,
        tasks,
        BlockingExecutor(),
        operations=(operation,),
        policy=synthetic_policy(),
    )
    if change in {"relink", "delete"}:
        job = await manager.async_enqueue_resource(
            service.ref, operation.operation, context=ExecutionContext()
        )
        if change == "relink":
            await registry.async_link_service(service.id, None)
        else:
            await registry.async_remove(service.id)
    elif change == "connection":
        job = await jobs.async_create(JobAction.UPDATE, host.id)
        await hosts.async_patch(host.id, HostPatch(address="changed.example.invalid"))
    else:
        task = await tasks.async_create(CustomTaskCreate(name="Test", argv=("true",)))
        job = await jobs.async_create(
            JobAction.CUSTOM_TASK, host.id, custom_task_id=task.id
        )
        await tasks.async_patch(task.id, CustomTaskPatch(argv=("false",)))
    await manager._async_run(job.id)
    assert (await jobs.async_get(job.id)).error_code == "execution_scope_changed"
    assert not operation.executed


@pytest.mark.parametrize("failure", ["exception", "exit"])
async def test_generic_failures_never_export_unvalidated_output(
    tmp_path: Path, failure: str
) -> None:
    _, hosts, _, tasks, jobs, _, service = await workspace(tmp_path)
    operation = SyntheticServiceOperation()
    if failure == "exception":
        operation.error = AutomationExecutionError(
            "untrusted-private-error", "private-provider-output"
        )
    else:
        operation.exit_code = 2
    manager = JobManager(
        jobs,
        hosts,
        tasks,
        BlockingExecutor(),
        operations=(operation,),
        policy=synthetic_policy(),
    )
    job = await manager.async_enqueue_resource(
        service.ref, operation.operation, context=ExecutionContext()
    )
    await manager._async_run(job.id)
    failed = await jobs.async_get(job.id)
    assert failed.state is JobState.FAILED
    assert failed.error_code == "resource_operation_failed"
    assert (
        "private"
        not in failed.model_dump_json() + (await jobs.async_log(job.id)).output
    )


async def test_restart_preserves_uncertain_logs_and_requires_explicit_review(
    tmp_path: Path,
) -> None:
    database, _, host, _, jobs, _, _ = await workspace(tmp_path)
    job = await jobs.async_create(
        JobAction.UPDATE, host.id, package_names=("vim", "curl")
    )
    assert await jobs.async_claim(job.id)
    await database.async_execute(
        "INSERT INTO job_logs VALUES(?,?,?)",
        (str(job.id), "bounded earlier evidence", 1),
    )
    assert await jobs.async_recover_queued() == ()
    failed = await jobs.async_get(job.id)
    assert failed.package_names == ("curl", "vim")
    assert failed.recovery_count == 1
    assert (await jobs.async_log(job.id)).output == "bounded earlier evidence"
    assert (await jobs.async_log(job.id)).truncated
    later = await jobs.async_create(
        JobAction.UPDATE, host.id, package_names=("vim", "curl")
    )
    await jobs.async_finish(
        later.id, state=JobState.SUCCESS, output="synthetic", truncated=False
    )
    assert (await jobs.async_get(job.id)).needs_review
    assert await jobs.async_recover_queued() == ()
    assert (await jobs.async_get(job.id)).recovery_count == 1
    await jobs.async_review(job.id)
    assert not (await jobs.async_get(job.id)).needs_review


@pytest.mark.parametrize("action", [JobAction.CHECK_UPDATES, JobAction.TEST_CONNECTION])
async def test_only_observational_legacy_work_may_resume(
    tmp_path: Path, action: JobAction
) -> None:
    _, _, host, _, jobs, _, _ = await workspace(tmp_path)
    job = await jobs.async_create(action, host.id)
    await jobs.async_claim(job.id)
    assert await jobs.async_recover_queued() == (job.id,)
    recovered = await jobs.async_get(job.id)
    assert recovered.started_at is None
    assert recovered.interrupted_at is not None
    assert recovered.recovery_count == 1
    assert recovered.execution == job.execution


async def test_immutable_scope_and_canonical_locks_survive_cancellation(
    tmp_path: Path,
) -> None:
    database, _, host, _, jobs, _, service = await workspace(tmp_path)
    job = await jobs.async_create(JobAction.UPDATE, host.id)
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        await database.async_execute(
            "UPDATE jobs SET execution_json=NULL WHERE id=?", (str(job.id),)
        )
    with pytest.raises(ValidationError, match="frozen"):
        job.execution.scope.operation = "synthetic.other"
    with pytest.raises(FrozenInstanceError):
        job.execution.scope.target.id = uuid4()
    locks = ResourceLocks()
    refs = (service.ref, host_ref := ResourceRef(ResourceKind.HOST, host.id))
    entered = asyncio.Event()

    async def waiter():
        entered.set()
        async with locks.hold(tuple(reversed(refs))):
            pass

    async with locks.hold(refs):
        task = asyncio.create_task(waiter())
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    async with asyncio.timeout(1), locks.hold((host_ref, service.ref)):
        pass


async def test_schema_12_upgrade_preserves_identity_state_and_references(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.homelab_backend.persistence import sqlite as storage
    from backend.homelab_backend.persistence.migrations import MIGRATIONS

    database = Database(tmp_path / "upgrade.db")
    monkeypatch.setattr(storage, "MIGRATIONS", MIGRATIONS[:12])
    await database.async_migrate()
    from backend.tests.legacy_fixtures import legacy_host

    host = await legacy_host(database)
    now = datetime.now(UTC).isoformat()
    identities = []
    for action, state in [
        (JobAction.UPDATE, JobState.RUNNING),
        (JobAction.REBOOT, JobState.QUEUED),
        (JobAction.CHECK_UPDATES, JobState.SUCCESS),
        (JobAction.CUSTOM_TASK, JobState.FAILED),
    ]:
        job_id = uuid4()
        identities.append(job_id)
        await database.async_execute(
            (
                "INSERT INTO jobs(id,action,host_id,state,created_at,started_at,"
                "reviewed_at,package_name,package_names_json) VALUES(?,?,?,?,?,?,?,?,?)"
            ),
            (
                str(job_id),
                action,
                str(host.id),
                state,
                now,
                now,
                now if state is JobState.FAILED else None,
                "vim" if action is JobAction.UPDATE else None,
                '["curl", "vim"]' if action is JobAction.REBOOT else "[]",
            ),
        )
        await database.async_execute(
            "INSERT INTO job_logs VALUES(?,?,0)", (str(job_id), "synthetic log")
        )
    before = await database.async_fetch_all("SELECT * FROM jobs ORDER BY id")
    monkeypatch.setattr(storage, "MIGRATIONS", MIGRATIONS)
    await database.async_migrate()
    await database.async_migrate()
    after = await database.async_fetch_all("SELECT * FROM jobs ORDER BY id")
    for original, migrated in zip(before, after, strict=True):
        assert all(migrated[key] == original[key] for key in dict(original))
    jobs = JobRepository(database)
    for job_id in identities:
        job = await jobs.async_get(job_id)
        assert job.id == job_id
        assert job.execution.scope.target == ResourceRef(ResourceKind.HOST, host.id)
        assert job.execution.context.caller is JobCaller.LEGACY_ADMIN
        assert (await jobs.async_log(job_id)).output == "synthetic log"
    assert (await jobs.async_get(identities[0])).state is JobState.RUNNING
    assert (await jobs.async_get(identities[1])).state is JobState.QUEUED


async def test_running_work_freezes_target_association_and_connection(
    tmp_path: Path,
) -> None:
    from backend.homelab_backend.contracts.resources import (
        RelationshipKind,
        ResourceRelationship,
    )
    from backend.homelab_backend.hosts import HostBusyError
    from backend.homelab_backend.resources.entities import RegistryConflict

    _, hosts, host, tasks, jobs, registry, service = await workspace(tmp_path)
    operation = SyntheticServiceOperation()
    operation.release.clear()
    manager = JobManager(
        jobs,
        hosts,
        tasks,
        BlockingExecutor(),
        operations=(operation,),
        policy=synthetic_policy(),
    )
    await manager.async_start()
    try:
        job = await manager.async_enqueue_resource(
            service.ref, operation.operation, context=ExecutionContext()
        )
        await asyncio.wait_for(operation.started.wait(), 5)
        with pytest.raises(RegistryConflict, match="running work"):
            await registry.async_link_service(service.id, None)
        with pytest.raises(RegistryConflict, match="running work"):
            await registry.async_remove(service.id)
        with pytest.raises(RegistryConflict, match="running work"):
            await registry.async_remove_relation(
                ResourceRelationship(
                    RelationshipKind.RUNS_SERVICE,
                    ResourceRef(ResourceKind.HOST, host.id),
                    service.ref,
                )
            )
        with pytest.raises(HostBusyError, match="running work"):
            await hosts.async_patch(
                host.id, HostPatch(address="changed.example.invalid")
            )
        with pytest.raises(HostBusyError, match="running work"):
            await hosts.async_delete(host.id)
        await hosts.async_patch(host.id, HostPatch(name="Renamed"))
        assert (await jobs.async_get(job.id)).state is JobState.RUNNING
        operation.release.set()
        await asyncio.wait_for(manager.async_wait_idle(), 5)
        await registry.async_link_service(service.id, None)
        assert await hosts.async_delete(host.id)
        persisted = await jobs.async_get(job.id)
        assert persisted.execution.scope.target == service.ref
        assert persisted.execution.scope.execution_host_id == host.id
    finally:
        operation.release.set()
        await manager.async_stop()


async def test_restart_manager_does_not_repeat_interrupted_update(
    tmp_path: Path,
) -> None:
    _, hosts, host, tasks, jobs, _, _ = await workspace(tmp_path)
    executor = BlockingExecutor()
    manager = JobManager(jobs, hosts, tasks, executor)
    await manager.async_start()
    first = await manager.async_enqueue(JobAction.UPDATE, host.id)
    await asyncio.wait_for(executor.first_started.wait(), 5)
    with pytest.raises(RuntimeError, match="already started"):
        await manager.async_start()
    await manager.async_stop()
    assert (await jobs.async_get(first.id)).state is JobState.RUNNING
    await manager.async_start()
    try:
        await asyncio.wait_for(manager.async_wait_idle(), 5)
        assert executor.calls == 1
        assert (await jobs.async_get(first.id)).error_code == "execution_interrupted"
        executor.release_first.set()
        later = await manager.async_enqueue(JobAction.UPDATE, host.id)
        await asyncio.wait_for(manager.async_wait_idle(), 5)
        assert executor.calls == 2
        assert (await jobs.async_get(later.id)).state is JobState.SUCCESS
    finally:
        await manager.async_stop()


async def test_scope_migration_failure_rolls_back_without_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.homelab_backend.persistence import sqlite as storage
    from backend.homelab_backend.persistence.migrations import MIGRATIONS

    database = Database(tmp_path / "rollback.db")
    monkeypatch.setattr(storage, "MIGRATIONS", MIGRATIONS[:12])
    await database.async_migrate()
    monkeypatch.setattr(
        storage,
        "MIGRATIONS",
        (*MIGRATIONS[:12], MIGRATIONS[12] + "INSERT INTO missing_table VALUES (1);"),
    )
    with pytest.raises(sqlite3.OperationalError, match="missing_table"):
        await database.async_migrate()
    assert (
        await database.async_fetch_one(
            "SELECT MAX(version) AS version FROM schema_migrations"
        )
    )["version"] == 12
    columns = await database.async_fetch_all("PRAGMA table_info(jobs)")
    assert "execution_json" not in {row["name"] for row in columns}
    monkeypatch.setattr(storage, "MIGRATIONS", MIGRATIONS)
    await database.async_migrate()
    assert (
        await database.async_fetch_one(
            "SELECT MAX(version) AS version FROM schema_migrations"
        )
    )["version"] == len(MIGRATIONS)


@pytest.mark.parametrize("ingress", [False, True])
def test_job_api_provenance_busy_errors_and_no_generic_bypass(
    tmp_path: Path, ingress: bool
) -> None:
    from backend.tests.test_backend_api import (
        AUTH,
        PendingExecutor,
        _client,
        _create_host,
        _csrf,
        _terminal_job,
        _ui_login,
    )

    class SelectionExecutor(PendingExecutor):
        selection: tuple[str, ...] = ()

        async def async_execute(
            self, action, host, package_name=None, *, package_names=()
        ):
            self.selection = package_names
            return await super().async_execute(action, host, package_name)

    executor = SelectionExecutor()
    with _client(tmp_path, executor, ingress_mode=ingress) as client:
        host = _create_host(client)
        host_id = host["id"]
        csrf = _csrf(client)
        if not ingress:
            _ui_login(client, csrf)
        url = f"/ui-api/hosts/{host_id}/actions/update"
        assert client.post(url).status_code == 403
        headers = {"X-CSRF-Token": csrf}
        invalid = client.post(
            url,
            headers=headers,
            json={
                "package_name": "vim",
                "caller": "external_admin",
                "approval_id": str(uuid4()),
            },
        )
        assert invalid.status_code == 422
        assert (
            client.post(
                f"/ui-api/hosts/{host_id}/actions/resource_operation", headers=headers
            ).status_code
            == 422
        )
        assert client.post(f"/api/v1/hosts/{host_id}/actions/update").status_code == 401
        created = client.post(
            url, headers=headers, json={"package_names": ["vim", "curl"]}
        )
        assert created.status_code == 202
        data = created.json()
        assert data["execution"]["context"]["caller"] == (
            "ingress_admin" if ingress else "ui_admin"
        )
        assert data["execution"]["scope"]["target"] == {"kind": "host", "id": host_id}
        assert data["execution"]["scope"]["package_names"] == ["curl", "vim"]
        assert data["package_names"] == ["curl", "vim"]
        assert client.portal is not None

        async def running():
            async with asyncio.timeout(5):
                while True:
                    response = await asyncio.to_thread(
                        client.get, f"/api/v1/jobs/{data['id']}", headers=AUTH
                    )
                    if response.json()["state"] == "running":
                        return

        client.portal.call(running)
        assert (
            client.patch(
                f"/api/v1/hosts/{host_id}",
                headers=AUTH,
                json={"address": "changed.example.invalid"},
            ).status_code
            == 409
        )
        assert (
            client.delete(f"/api/v1/hosts/{host_id}", headers=AUTH).status_code == 409
        )
        assert (
            client.patch(
                f"/ui-api/hosts/{host_id}",
                headers=headers,
                json={"address": "changed.example.invalid"},
            ).status_code
            == 409
        )
        assert (
            client.delete(f"/ui-api/hosts/{host_id}", headers=headers).status_code
            == 409
        )
        client.portal.call(executor.async_release)
        assert _terminal_job(client, data["id"])["state"] == "success"
        assert executor.selection == ("curl", "vim")
        external = client.post(
            f"/api/v1/hosts/{host_id}/actions/check-updates", headers=AUTH
        )
        assert external.status_code == 202
        assert external.json()["execution"]["context"]["caller"] == "external_admin"
        assert "authorization" not in str(external.json()).lower()


async def test_service_failure_review_is_not_resolved_by_a_sibling_success(
    tmp_path: Path,
) -> None:
    _, hosts, host, tasks, jobs, registry, service = await workspace(tmp_path)
    sibling = await registry.async_create_service(
        "Sibling",
        "synthetic",
        ProviderBinding("synthetic.test", uuid4(), "demo_02"),
        host.id,
    )
    operation = SyntheticServiceOperation()
    manager = JobManager(
        jobs,
        hosts,
        tasks,
        BlockingExecutor(),
        operations=(operation,),
        policy=synthetic_policy(),
    )
    failed = await manager.async_enqueue_resource(
        service.ref, operation.operation, context=ExecutionContext()
    )
    operation.exit_code = 1
    await manager._async_run(failed.id)
    operation.exit_code = 0
    success = await manager.async_enqueue_resource(
        sibling.ref, operation.operation, context=ExecutionContext()
    )
    await manager._async_run(success.id)
    assert (await jobs.async_get(failed.id)).needs_review
    matching = await manager.async_enqueue_resource(
        service.ref, operation.operation, context=ExecutionContext()
    )
    await manager._async_run(matching.id)
    assert not (await jobs.async_get(failed.id)).needs_review


async def test_legacy_parameter_tampering_cannot_change_execution_scope(
    tmp_path: Path,
) -> None:
    database, hosts, host, tasks, jobs, _, _ = await workspace(tmp_path)
    job = await jobs.async_create(JobAction.UPDATE, host.id, package_name="vim")
    await database.async_execute(
        "UPDATE jobs SET package_name='curl' WHERE id=?", (str(job.id),)
    )
    executor = BlockingExecutor()
    manager = JobManager(jobs, hosts, tasks, executor)
    await manager._async_run(job.id)
    assert executor.calls == 0
    assert (await jobs.async_get(job.id)).error_code == "execution_scope_changed"


@pytest.mark.parametrize(
    "invalid", ["conflicts", "both_packages", "duplicates", "unsafe_package"]
)
def test_scope_rejects_ambiguous_or_unvalidated_inputs(invalid: str) -> None:
    target = ResourceRef(ResourceKind.HOST, uuid4())
    values = {"target": target, "conflicts": (target,), "operation": "linux.update"}
    if invalid == "conflicts":
        values["conflicts"] = (ResourceRef(ResourceKind.HOST, uuid4()),)
    elif invalid == "both_packages":
        values.update(package_name="vim", package_names=("curl",))
    elif invalid == "duplicates":
        values["package_names"] = ("vim", "vim")
    else:
        values["package_name"] = "vim; unsafe"
    with pytest.raises(ValidationError):
        OperationScope.model_validate(values)


async def test_repository_rejects_target_and_parameter_bypasses(tmp_path: Path) -> None:
    _, _, host, _, jobs, _, service = await workspace(tmp_path)
    for action, host_id, kwargs in (
        (JobAction.UPDATE, None, {}),
        (JobAction.UPDATE, host.id, {"context": ExecutionContext(approval_id=uuid4())}),
        (JobAction.UPDATE, host.id, {"target": service.ref}),
        (JobAction.RESOURCE_OPERATION, None, {"target": service.ref}),
        (
            JobAction.RESOURCE_OPERATION,
            None,
            {
                "target": service.ref,
                "operation": "synthetic.update",
                "package_name": "vim",
            },
        ),
    ):
        with pytest.raises(
            ValueError, match=r"Target required|Legacy action|Generic operation"
        ):
            await jobs.async_create(action, host_id, **kwargs)
    assert await jobs.async_count() == 0


async def test_association_change_during_enqueue_authorization_cannot_expand_targets(
    tmp_path: Path,
) -> None:
    _, hosts, _, tasks, jobs, registry, service = await workspace(tmp_path)
    operation = SyntheticServiceOperation()

    async def change_during_authorization(scope, context):
        await registry.async_link_service(service.id, None)
        return True

    operation.async_authorize = change_during_authorization
    manager = JobManager(
        jobs,
        hosts,
        tasks,
        BlockingExecutor(),
        operations=(operation,),
        policy=synthetic_policy(),
    )
    with pytest.raises(ValueError, match="changed while queueing"):
        await manager.async_enqueue_resource(
            service.ref, operation.operation, context=ExecutionContext()
        )
    failed = (await jobs.async_list())[0]
    assert failed.error_code == "execution_scope_changed"
    assert not operation.executed


async def test_worker_survives_a_transient_read_failure_without_leaking_details(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from unittest.mock import patch

    _, hosts, host, tasks, jobs, _, _ = await workspace(tmp_path)
    executor = BlockingExecutor()
    executor.release_first.set()
    manager = JobManager(jobs, hosts, tasks, executor, worker_count=1)
    original_get = jobs.async_get
    first_read = True

    async def fail_once(job_id):
        nonlocal first_read
        if first_read:
            first_read = False
            raise RuntimeError("private synthetic persistence detail")
        return await original_get(job_id)

    await manager.async_start()
    try:
        with patch.object(jobs, "async_get", fail_once):
            first = await manager.async_enqueue(JobAction.UPDATE, host.id)
            second = await manager.async_enqueue(JobAction.CHECK_UPDATES, host.id)
            await asyncio.wait_for(manager.async_wait_idle(), 5)
        assert (await jobs.async_get(first.id)).error_code == "internal_execution_error"
        assert (await jobs.async_get(second.id)).state is JobState.SUCCESS
        assert executor.calls == 1
        assert (
            "private synthetic"
            not in caplog.text + (await jobs.async_log(first.id)).output
        )
    finally:
        await manager.async_stop()
