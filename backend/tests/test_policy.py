"""Synthetic default-deny and authenticated-use-case bypass contracts."""

from pathlib import Path
from uuid import uuid4

import pytest

from backend.homelab_backend.contracts.capabilities import RiskClass
from backend.homelab_backend.contracts.resources import ResourceKind, ResourceRef
from backend.homelab_backend.database import Database
from backend.homelab_backend.execution.scope import ExecutionContext, JobCaller
from backend.homelab_backend.groups.application import GroupService
from backend.homelab_backend.groups.entities import Group
from backend.homelab_backend.groups.repository import SqliteGroupStore
from backend.homelab_backend.jobs import JobManager
from backend.homelab_backend.models import HostCreate, JobAction
from backend.homelab_backend.policy.application import (
    AuthorizationDenied,
    current_principal,
    principal_scope,
)
from backend.homelab_backend.policy.domain import (
    ANONYMOUS,
    SYSTEM,
    AuthSource,
    OperationPolicy,
    Permission,
    PolicyEngine,
    Principal,
    PrincipalKind,
    entrance,
)
from backend.homelab_backend.policy.store import policy_for
from backend.homelab_backend.resources.application import ResourceRegistry
from backend.homelab_backend.resources.repository import SqliteResourceRepository
from backend.tests.test_jobs import BlockingExecutor
from backend.tests.test_resource_jobs import workspace

AGENT = Principal(uuid4(), PrincipalKind.AGENT, AuthSource.AGENT)
AUTOMATION = Principal(uuid4(), PrincipalKind.AUTOMATION, AuthSource.AUTOMATION)
HUMAN = entrance(PrincipalKind.HUMAN, AuthSource.UI)
ADMIN = entrance(PrincipalKind.ADMIN, AuthSource.API)
STATUS = entrance(PrincipalKind.STATUS, AuthSource.INTERNAL)


@pytest.mark.parametrize("actor", [ANONYMOUS, AGENT, AUTOMATION, STATUS])
@pytest.mark.parametrize(
    "permission",
    [
        Permission.HOST_WRITE,
        Permission.TASK_WRITE,
        Permission.RESOURCE_WRITE,
        Permission.SSH_IDENTITY,
        Permission.APPROVAL_DECIDE,
    ],
)
def test_restricted_identity_cannot_inherit_admin(
    actor: Principal, permission: Permission
) -> None:
    assert not PolicyEngine().decide(actor, permission).allowed


def test_unknown_contracts_and_forged_authority_fail_closed() -> None:
    engine = PolicyEngine()
    target = ResourceRef(ResourceKind.HOST, uuid4())
    assert not engine.decide(SYSTEM, "arbitrary.permission").allowed
    assert not engine.decide(
        SYSTEM, Permission.EXECUTE, target, "unknown.operation"
    ).allowed
    assert not engine.decide(SYSTEM, Permission.EXECUTE).allowed
    assert not engine.decide(STATUS, Permission.EXECUTE, target, "linux.reboot").allowed
    assert engine.decide(
        STATUS, Permission.EXECUTE, target, "linux.check_updates"
    ).allowed
    assert not engine.decide(
        AGENT, Permission.APPROVAL_REQUEST, target, "unknown.operation"
    ).allowed
    assert not engine.decide(ADMIN, Permission.APPROVAL_DECIDE).allowed
    assert not engine.decide(HUMAN, Permission.LEGACY_API).allowed
    assert not engine.decide(SYSTEM, Permission.LEGACY_API).allowed
    assert engine.decide(ADMIN, Permission.LEGACY_API).allowed
    assert engine.decide(HUMAN, Permission.APPROVAL_DECIDE).allowed
    with pytest.raises(ValueError, match="authority source"):
        Principal(uuid4(), PrincipalKind.HUMAN, AuthSource.AGENT)
    with pytest.raises(ValueError, match="Legacy authority"):
        OperationPolicy(
            "future.update", frozenset({ResourceKind.HOST}), RiskClass.MUTATING, True
        )
    with pytest.raises(ValueError, match="Invalid operation"):
        OperationPolicy(
            "raw unsafe string", frozenset({ResourceKind.HOST}), RiskClass.MUTATING
        )
    with pytest.raises(ValueError, match="Duplicate"):
        PolicyEngine((
            OperationPolicy(
                "linux.update", frozenset({ResourceKind.HOST}), RiskClass.READ_ONLY
            ),
        ))


async def test_agent_direct_service_calls_are_denied_and_audited(
    tmp_path: Path,
) -> None:
    _, hosts, host, tasks, jobs, registry, service = await workspace(tmp_path)
    database = jobs._database
    guard = policy_for(database)
    groups = GroupService(SqliteGroupStore(database), guard)
    registry = ResourceRegistry(SqliteResourceRepository(database), guard)
    executor = BlockingExecutor()
    manager = JobManager(jobs, hosts, tasks, executor)
    from backend.homelab_backend.models import CustomTaskCreate, HostPatch
    from backend.homelab_backend.task_compatibility import TaskCompatibilityService
    from backend.homelab_backend.visible_checks import (
        HostCheckPreferences,
        VisibleChecks,
    )

    compatibility = TaskCompatibilityService(database, tasks, hosts, executor)
    visible = VisibleChecks(database, hosts, manager)
    operations = [
        lambda: hosts.async_create(
            HostCreate(
                name="Other", address="other.example.invalid", username="automation"
            )
        ),
        lambda: hosts.async_patch(host.id, HostPatch(name="Changed")),
        lambda: hosts.async_delete(host.id),
        lambda: tasks.async_create(
            CustomTaskCreate(
                name="Unsafe", mode="shell", shell_command="printf synthetic"
            )
        ),
        lambda: tasks.async_delete(uuid4()),
        lambda: compatibility.async_check(uuid4(), host.id),
        lambda: compatibility.async_assign(uuid4(), host.id, enabled=True),
        lambda: compatibility.async_unassign(uuid4(), host.id),
        lambda: visible.async_update(HostCheckPreferences(enabled=False)),
        lambda: visible.async_check(),
        lambda: groups.async_save(Group(uuid4(), "Test", "", None, ()), create=True),
        lambda: groups.async_delete(uuid4()),
        lambda: groups.async_tags(host.id, frozenset({"production"})),
        lambda: registry.async_link_service(service.id, None),
        lambda: registry.async_remove(service.id),
        lambda: jobs.async_review(uuid4()),
        lambda: manager.async_enqueue(
            JobAction.UPDATE,
            host.id,
            context=ExecutionContext(caller=JobCaller.UI_ADMIN),
        ),
        lambda: manager.async_enqueue_custom(
            uuid4(), host.id, context=ExecutionContext(caller=JobCaller.UI_ADMIN)
        ),
    ]
    with principal_scope(AGENT):
        for operation in operations:
            with pytest.raises(AuthorizationDenied, match="not permitted"):
                await operation()
    assert current_principal() == SYSTEM
    assert executor.calls == 0
    assert await jobs.async_count() == 0
    assert (await hosts.async_get(host.id)).name == host.name
    events = await database.async_fetch_all("SELECT * FROM authorization_events")
    assert len(events) == len(operations)
    assert all(row["principal_id"] == str(AGENT.id) for row in events)
    assert all(row["code"] == "policy_denied" for row in events)
    assert "other.example.invalid" not in str([dict(row) for row in events])


async def test_worker_does_not_upgrade_queued_agent_identity(tmp_path: Path) -> None:
    _, hosts, host, tasks, jobs, _, _ = await workspace(tmp_path)
    job = await jobs.async_create(
        JobAction.UPDATE,
        host.id,
        context=ExecutionContext(caller=JobCaller.UI_ADMIN, principal=AGENT),
    )
    executor = BlockingExecutor()
    await JobManager(jobs, hosts, tasks, executor)._async_run(job.id)
    persisted = await jobs.async_get(job.id)
    assert persisted.error_code == "policy_denied"
    assert persisted.execution.context.principal == AGENT
    assert executor.calls == 0
    assert current_principal() == SYSTEM


def test_agent_credential_cannot_reach_legacy_api_or_human_login(
    tmp_path: Path,
) -> None:
    from fastapi.testclient import TestClient

    from backend.homelab_backend.app import create_app
    from backend.homelab_backend.config import Settings
    from backend.tests.test_backend_api import TOKEN, FakeExecutor, _csrf

    token = "synthetic-agent-credential-for-contract-tests"

    class Resolver:
        async def async_authenticate(self, value: str) -> Principal | None:
            return AGENT if value == token else None

    executor = FakeExecutor()
    app = create_app(
        Settings(data_dir=tmp_path, api_token=TOKEN),
        executor=executor,
        principal_resolver=Resolver(),
    )
    with TestClient(app) as client:
        for method, path, body in [
            (
                "POST",
                "/api/v1/hosts",
                {
                    "name": "Test",
                    "address": "node-01.example.invalid",
                    "username": "automation",
                },
            ),
            ("POST", f"/api/v1/hosts/{uuid4()}/actions/reboot", None),
            (
                "POST",
                "/api/v1/custom-tasks",
                {
                    "name": "Unsafe",
                    "mode": "shell",
                    "shell_command": "printf synthetic",
                },
            ),
            ("GET", "/api/v1/public-key", None),
            ("POST", "/api/v1/actions/check", None),
        ]:
            response = client.request(
                method,
                path,
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Principal-Kind": "human",
                    "X-Approval-ID": str(uuid4()),
                },
                json=body,
            )
            assert response.status_code == 403, (path, response.text)
            assert response.json()["error_code"] == "policy_denied"
            assert token not in response.text
        assert (
            client.post(
                "/ui-api/auth/login",
                headers={"X-CSRF-Token": _csrf(client)},
                json={"api_token": token},
            ).status_code
            == 401
        )
        assert (
            client.get(
                "/api/v1/info", headers={"Authorization": "Bearer unknown-credential"}
            ).status_code
            == 401
        )
        assert (
            client.get(
                "/api/v1/info", headers={"Authorization": f"Bearer {TOKEN}"}
            ).status_code
            == 200
        )
        assert executor.calls == []


def test_missing_http_dependency_never_inherits_internal_authority(
    tmp_path: Path,
) -> None:
    from fastapi.testclient import TestClient

    from backend.homelab_backend.app import create_app
    from backend.homelab_backend.config import Settings
    from backend.homelab_backend.hosts import HostRepository
    from backend.tests.test_backend_api import AUTH, TOKEN, FakeExecutor

    settings = Settings(data_dir=tmp_path, api_token=TOKEN)
    app = create_app(settings, executor=FakeExecutor())
    hosts = HostRepository(Database(settings.database_path))

    @app.post("/unprotected-test-write")
    async def unprotected():
        return await hosts.async_create(
            HostCreate(
                name="Test", address="node-01.example.invalid", username="automation"
            )
        )

    with TestClient(app) as client:
        assert client.get("/api/v1/info", headers=AUTH).status_code == 200
        assert client.post("/unprotected-test-write", headers=AUTH).status_code == 403
        assert client.get("/api/v1/hosts", headers=AUTH).json() == []
    assert current_principal() == SYSTEM
