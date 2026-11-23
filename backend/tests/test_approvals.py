"""No real providers: immutable human approval, replay and state-race contracts."""

import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.homelab_backend.contracts.capabilities import RiskClass
from backend.homelab_backend.contracts.resources import ResourceKind, ResourceRef
from backend.homelab_backend.execution.authorization import scope_digest
from backend.homelab_backend.execution.scope import ExecutionContext, JobCaller
from backend.homelab_backend.jobs import JobManager
from backend.homelab_backend.policy.application import (
    AuthorizationDenied,
    PolicyGuard,
    principal_scope,
)
from backend.homelab_backend.policy.approvals import (
    ApprovalRequest,
    ApprovalService,
    ApprovalState,
)
from backend.homelab_backend.policy.domain import (
    ANONYMOUS,
    SYSTEM,
    AuthSource,
    OperationPolicy,
    PolicyEngine,
    Principal,
    PrincipalKind,
)
from backend.homelab_backend.policy.store import SqlitePolicyStore
from backend.tests.test_jobs import BlockingExecutor
from backend.tests.test_policy import ADMIN, AGENT, AUTOMATION, HUMAN
from backend.tests.test_resource_jobs import SyntheticServiceOperation, workspace

OPERATION = "synthetic.service_restore"


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 17, 12, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


class Validator:
    def __init__(self) -> None:
        self.valid = True

    async def async_is_current(self, request: ApprovalRequest) -> bool:
        return self.valid and request.observed_state == "a" * 64


class Restore(SyntheticServiceOperation):
    operation = OPERATION

    async def async_authorize(self, scope, context) -> bool:
        return True  # Feature readiness cannot override the central policy.


def guard_for(store: SqlitePolicyStore) -> PolicyGuard:
    return PolicyGuard(
        store,
        engine=PolicyEngine((
            OperationPolicy(
                OPERATION,
                frozenset({ResourceKind.MANAGED_SERVICE}),
                RiskClass.DESTRUCTIVE,
            ),
        )),
    )


async def approval_workspace(tmp_path: Path):
    database, hosts, host, tasks, jobs, registry, resource = await workspace(tmp_path)
    store = SqlitePolicyStore(database)
    guard = guard_for(store)
    clock = Clock()
    validator = Validator()
    approvals = ApprovalService(store, guard, validator, clock=clock)
    scope = await jobs.async_prepare_resource(resource.ref, OPERATION)
    with principal_scope(ADMIN):
        record = await approvals.async_request(
            resource.ref, OPERATION, scope_digest(scope), "a" * 64
        )
    with principal_scope(HUMAN):
        await approvals.async_decide(record.request.id, approve=True)
    return (
        database,
        hosts,
        host,
        tasks,
        jobs,
        registry,
        resource,
        store,
        guard,
        clock,
        validator,
        approvals,
        scope,
        record,
    )


async def test_protected_job_requires_exact_human_approval_and_consumes_once(
    tmp_path: Path,
) -> None:
    (
        database,
        hosts,
        _,
        tasks,
        jobs,
        _,
        resource,
        store,
        guard,
        _,
        _,
        approvals,
        _scope,
        record,
    ) = await approval_workspace(tmp_path)
    handler = Restore()
    manager = JobManager(
        jobs,
        hosts,
        tasks,
        BlockingExecutor(),
        operations=(handler,),
        policy=guard,
        approvals=approvals,
    )
    with principal_scope(ADMIN):
        with pytest.raises(AuthorizationDenied, match="not permitted"):
            await manager.async_enqueue_resource(
                resource.ref,
                OPERATION,
                context=ExecutionContext(caller=JobCaller.EXTERNAL_ADMIN),
            )
        assert await jobs.async_count() == 0
        job = await manager.async_enqueue_resource(
            resource.ref,
            OPERATION,
            context=ExecutionContext(
                caller=JobCaller.EXTERNAL_ADMIN, approval_id=record.request.id
            ),
        )
    assert (await store.async_get(record.request.id)).state is ApprovalState.APPROVED
    await manager._async_run(job.id)
    assert (await jobs.async_get(job.id)).state == "success"
    consumed = await store.async_get(record.request.id)
    assert consumed.state is ApprovalState.CONSUMED
    assert consumed.consumed_by_job == job.id
    assert handler.executed == [resource.id]
    with (
        principal_scope(ADMIN),
        pytest.raises(AuthorizationDenied, match="not permitted"),
    ):
        await manager.async_enqueue_resource(
            resource.ref,
            OPERATION,
            context=ExecutionContext(
                caller=JobCaller.EXTERNAL_ADMIN, approval_id=record.request.id
            ),
        )
    assert await jobs.async_count() == 1
    codes = {
        row["code"]
        for row in await database.async_fetch_all(
            "SELECT code FROM authorization_events"
        )
    }
    assert {
        "approved",
        "approval_consumed",
        "human_approval_required",
        "approval_unavailable",
    } <= codes


@pytest.mark.parametrize(
    "change", ["scope", "target", "actor", "expiry", "state", "operation"]
)
async def test_approval_is_not_a_bearer_grant(tmp_path: Path, change: str) -> None:
    (
        _,
        _,
        _,
        _,
        _,
        _,
        resource,
        store,
        _,
        clock,
        validator,
        approvals,
        scope,
        record,
    ) = await approval_workspace(tmp_path)
    actor = ADMIN
    target = resource.ref
    operation = OPERATION
    digest = scope_digest(scope)
    if change == "scope":
        digest = "b" * 64
    elif change == "target":
        target = ResourceRef(ResourceKind.MANAGED_SERVICE, uuid4())
    elif change == "actor":
        actor = Principal(uuid4(), PrincipalKind.ADMIN, AuthSource.API)
    elif change == "expiry":
        clock.now += timedelta(minutes=16)
    elif change == "state":
        validator.valid = False
    else:
        operation = "unknown.restore"
    with (
        principal_scope(actor),
        pytest.raises(AuthorizationDenied, match="not permitted"),
    ):
        await approvals.async_consume(
            record.request.id, target, operation, digest, uuid4()
        )
    assert (await store.async_get(record.request.id)).consumed_by_job is None


async def test_double_consumption_is_atomic_across_services(tmp_path: Path) -> None:
    (
        _,
        _,
        _,
        _,
        _,
        _,
        resource,
        store,
        guard,
        clock,
        validator,
        approvals,
        scope,
        record,
    ) = await approval_workspace(tmp_path)
    other = ApprovalService(store, guard, validator, clock=clock)
    first, second = uuid4(), uuid4()
    with principal_scope(ADMIN):
        outcomes = await asyncio.gather(
            approvals.async_consume(
                record.request.id, resource.ref, OPERATION, scope_digest(scope), first
            ),
            other.async_consume(
                record.request.id, resource.ref, OPERATION, scope_digest(scope), second
            ),
            return_exceptions=True,
        )
    assert sum(x is None for x in outcomes) == 1
    assert sum(isinstance(x, AuthorizationDenied) for x in outcomes) == 1
    assert (await store.async_get(record.request.id)).consumed_by_job in {first, second}


@pytest.mark.parametrize("actor", [AGENT, AUTOMATION, ADMIN, SYSTEM, ANONYMOUS])
async def test_only_authenticated_human_ui_can_decide(
    tmp_path: Path, actor: Principal
) -> None:
    (
        _,
        _,
        _,
        _,
        _,
        _,
        _,
        store,
        _,
        _,
        _,
        approvals,
        _,
        record,
    ) = await approval_workspace(tmp_path)
    with (
        principal_scope(actor),
        pytest.raises(AuthorizationDenied, match="not permitted"),
    ):
        await approvals.async_decide(record.request.id, approve=True)
    assert (await store.async_get(record.request.id)).decided_by == HUMAN.id


async def test_agent_proposal_does_not_enable_execution_or_self_approval(
    tmp_path: Path,
) -> None:
    (
        _,
        _,
        _,
        _,
        _,
        _,
        resource,
        store,
        _,
        _,
        _,
        approvals,
        scope,
        _,
    ) = await approval_workspace(tmp_path)
    with principal_scope(AGENT):
        pending = await approvals.async_request(
            resource.ref, OPERATION, scope_digest(scope), "a" * 64
        )
        with pytest.raises(AuthorizationDenied, match="not permitted"):
            await approvals.async_decide(pending.request.id, approve=True)
    with principal_scope(HUMAN):
        await approvals.async_decide(pending.request.id, approve=True)
    with (
        principal_scope(AGENT),
        pytest.raises(AuthorizationDenied, match="not permitted"),
    ):
        await approvals.async_consume(
            pending.request.id, resource.ref, OPERATION, scope_digest(scope), uuid4()
        )
    assert (await store.async_get(pending.request.id)).state is ApprovalState.APPROVED


async def test_expiration_rejection_and_request_immutability(tmp_path: Path) -> None:
    (
        database,
        _,
        _,
        _,
        _,
        _,
        resource,
        store,
        _,
        clock,
        _,
        approvals,
        scope,
        record,
    ) = await approval_workspace(tmp_path)
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        await database.async_execute(
            "UPDATE approval_requests SET request_json='{}' WHERE id=?",
            (str(record.request.id),),
        )
    with pytest.raises(ValidationError, match="frozen"):
        record.request.scope_digest = "c" * 64
    with principal_scope(ADMIN):
        for duration in (timedelta(0), timedelta(hours=1)):
            with pytest.raises(ValueError, match="fifteen minutes"):
                await approvals.async_request(
                    resource.ref,
                    OPERATION,
                    scope_digest(scope),
                    "a" * 64,
                    lifetime=duration,
                )
        pending = await approvals.async_request(
            resource.ref, OPERATION, scope_digest(scope), "a" * 64
        )
        rejected = await approvals.async_request(
            resource.ref, OPERATION, scope_digest(scope), "a" * 64
        )
    with principal_scope(HUMAN):
        await approvals.async_decide(rejected.request.id, approve=False)
        with pytest.raises(AuthorizationDenied, match="not permitted"):
            await approvals.async_decide(rejected.request.id, approve=True)
        clock.now += timedelta(minutes=16)
        with pytest.raises(AuthorizationDenied, match="not permitted"):
            await approvals.async_decide(pending.request.id, approve=True)
        with pytest.raises(AuthorizationDenied, match="not permitted"):
            await approvals.async_decide(uuid4(), approve=True)
    assert (await store.async_get(pending.request.id)).state is ApprovalState.EXPIRED
    assert (await store.async_get(rejected.request.id)).state is ApprovalState.REJECTED


async def test_changed_state_before_dispatch_never_consumes_or_executes(
    tmp_path: Path,
) -> None:
    (
        _,
        hosts,
        _,
        tasks,
        jobs,
        _,
        resource,
        store,
        guard,
        _,
        validator,
        approvals,
        _,
        record,
    ) = await approval_workspace(tmp_path)
    handler = Restore()
    manager = JobManager(
        jobs,
        hosts,
        tasks,
        BlockingExecutor(),
        operations=(handler,),
        policy=guard,
        approvals=approvals,
    )
    with principal_scope(ADMIN):
        job = await manager.async_enqueue_resource(
            resource.ref,
            OPERATION,
            context=ExecutionContext(
                caller=JobCaller.EXTERNAL_ADMIN, approval_id=record.request.id
            ),
        )
    validator.valid = False
    await manager._async_run(job.id)
    assert (await jobs.async_get(job.id)).error_code == "policy_denied"
    assert not handler.executed
    assert (await store.async_get(record.request.id)).state is ApprovalState.APPROVED


async def test_schema_14_is_additive_atomic_and_old_queued_authority_survives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from backend.homelab_backend.custom_tasks import CustomTaskRepository
    from backend.homelab_backend.database import Database
    from backend.homelab_backend.hosts import HostRepository
    from backend.homelab_backend.jobs import JobRepository
    from backend.homelab_backend.persistence import sqlite as storage
    from backend.homelab_backend.persistence.migrations import MIGRATIONS

    database = Database(tmp_path / "upgrade.db")
    monkeypatch.setattr(storage, "MIGRATIONS", MIGRATIONS[:13])
    await database.async_migrate()
    hosts = HostRepository(database)
    from backend.tests.legacy_fixtures import legacy_host, legacy_update_scope

    host = await legacy_host(database)
    jobs = JobRepository(database)
    scope = legacy_update_scope(host)
    job_id = uuid4()
    now = datetime.now(UTC).isoformat()
    old_json = json.dumps({
        "scope": scope.model_dump(mode="json"),
        "context": {"caller": "external_admin", "approval_id": None},
    })
    await database.async_execute(
        "INSERT INTO jobs(id,action,host_id,state,created_at,execution_json) "
        "VALUES(?,?,?,?,?,?)",
        (str(job_id), "update", str(host.id), "queued", now, old_json),
    )
    before = dict(
        await database.async_fetch_one("SELECT * FROM jobs WHERE id=?", (str(job_id),))
    )
    monkeypatch.setattr(
        storage,
        "MIGRATIONS",
        (*MIGRATIONS[:13], MIGRATIONS[13] + "INSERT INTO missing_table VALUES(1);"),
    )
    with pytest.raises(sqlite3.OperationalError, match="missing_table"):
        await database.async_migrate()
    assert (
        await database.async_fetch_one(
            "SELECT name FROM sqlite_master WHERE name='authorization_events'"
        )
        is None
    )
    monkeypatch.setattr(storage, "MIGRATIONS", MIGRATIONS)
    await database.async_migrate()
    await database.async_migrate()
    assert before == dict(
        await database.async_fetch_one("SELECT * FROM jobs WHERE id=?", (str(job_id),))
    )
    executor = BlockingExecutor()
    executor.release_first.set()
    manager = JobManager(
        jobs, hosts, CustomTaskRepository(database, allow_shell=False), executor
    )
    await manager.async_start()
    try:
        await asyncio.wait_for(manager.async_wait_idle(), 5)
    finally:
        await manager.async_stop()
    result = await jobs.async_get(job_id)
    assert result.state == "success"
    assert result.execution.context.principal is None
    assert result.execution.context.caller is JobCaller.EXTERNAL_ADMIN
    assert result.id == job_id
    assert executor.calls == 1


@pytest.mark.parametrize("actor", [AGENT, AUTOMATION, ANONYMOUS])
async def test_feature_readiness_never_overrides_central_denial(
    tmp_path: Path, actor: Principal
) -> None:
    (
        _,
        hosts,
        _,
        tasks,
        jobs,
        _,
        resource,
        _,
        guard,
        _,
        _,
        approvals,
        _,
        record,
    ) = await approval_workspace(tmp_path)
    handler = Restore()
    manager = JobManager(
        jobs,
        hosts,
        tasks,
        BlockingExecutor(),
        operations=(handler,),
        policy=guard,
        approvals=approvals,
    )
    with (
        principal_scope(actor),
        pytest.raises(AuthorizationDenied, match="not permitted"),
    ):
        await manager.async_enqueue_resource(
            resource.ref,
            OPERATION,
            context=ExecutionContext(
                caller=JobCaller.UI_ADMIN,
                approval_id=record.request.id,
                principal=HUMAN,
            ),
        )
    assert await jobs.async_count() == 0
    assert not handler.executed


async def test_consumed_approval_is_not_rearmed_after_interrupted_execution(
    tmp_path: Path,
) -> None:
    (
        _,
        hosts,
        _,
        tasks,
        jobs,
        _,
        resource,
        store,
        guard,
        _,
        _,
        approvals,
        _,
        record,
    ) = await approval_workspace(tmp_path)
    handler = Restore()
    handler.release.clear()
    manager = JobManager(
        jobs,
        hosts,
        tasks,
        BlockingExecutor(),
        operations=(handler,),
        policy=guard,
        approvals=approvals,
    )
    with principal_scope(ADMIN):
        job = await manager.async_enqueue_resource(
            resource.ref,
            OPERATION,
            context=ExecutionContext(
                caller=JobCaller.EXTERNAL_ADMIN, approval_id=record.request.id
            ),
        )
    await manager.async_start()
    try:
        await asyncio.wait_for(handler.started.wait(), 5)
        assert (
            await store.async_get(record.request.id)
        ).state is ApprovalState.CONSUMED
    finally:
        await manager.async_stop()
    await manager.async_start()
    try:
        await asyncio.wait_for(manager.async_wait_idle(), 5)
        assert (await jobs.async_get(job.id)).error_code == "execution_interrupted"
        assert handler.executed == [resource.id]
        assert (await store.async_get(record.request.id)).consumed_by_job == job.id
    finally:
        await manager.async_stop()


async def test_one_job_cannot_consume_two_approvals(tmp_path: Path) -> None:
    (
        _,
        _,
        _,
        _,
        _,
        _,
        resource,
        _,
        _,
        _,
        _,
        approvals,
        scope,
        first,
    ) = await approval_workspace(tmp_path)
    with principal_scope(ADMIN):
        second = await approvals.async_request(
            resource.ref, OPERATION, scope_digest(scope), "a" * 64
        )
    with principal_scope(HUMAN):
        await approvals.async_decide(second.request.id, approve=True)
    job_id = uuid4()
    with principal_scope(ADMIN):
        await approvals.async_consume(
            first.request.id, resource.ref, OPERATION, scope_digest(scope), job_id
        )
        with pytest.raises(AuthorizationDenied, match="not permitted"):
            await approvals.async_consume(
                second.request.id, resource.ref, OPERATION, scope_digest(scope), job_id
            )
