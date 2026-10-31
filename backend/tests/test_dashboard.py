"""Dashboard, prerequisite policy, migrations and onboarding regression tests."""

import builtins
import json
import os
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from backend.homelab_backend.automation import (
    _PROBE_SCRIPT,
    AnsibleExecutor,
    AutomationExecutionError,
)
from backend.homelab_backend.custom_tasks import CustomTaskRepository
from backend.homelab_backend.dashboard import DashboardService
from backend.homelab_backend.database import _MIGRATIONS, Database
from backend.homelab_backend.hosts import HostRepository
from backend.homelab_backend.jobs import JobManager, JobRepository
from backend.homelab_backend.models import (
    CustomTaskCreate,
    CustomTaskPatch,
    HostCreate,
    HostPatch,
    JobAction,
    JobState,
    ProbeFacts,
    TaskRequirements,
)
from backend.homelab_backend.onboarding import setup_command
from backend.homelab_backend.task_compatibility import TaskCompatibilityService
from backend.tests.test_backend_api import (
    AUTH,
    FakeExecutor,
    _client,
    _create_host,
    _csrf,
    _terminal_job,
)


async def _services(tmp_path: Path):
    database = Database(tmp_path / "test.db")
    await database.async_migrate()
    hosts = HostRepository(database)
    tasks = CustomTaskRepository(database, allow_shell=True)
    executor = FakeExecutor()
    service = TaskCompatibilityService(database, tasks, hosts, executor)
    host = await hosts.async_create(
        HostCreate(
            name="Node 01", address="node-01.example.invalid", username="automation"
        )
    )
    task = await tasks.async_create(
        CustomTaskCreate(name="Read uptime", argv=("uptime",))
    )
    return database, hosts, tasks, executor, service, host, task


async def test_compatibility_assignment_lifecycle_and_invalidation(
    tmp_path: Path,
) -> None:
    database, hosts, tasks, executor, service, host, task = await _services(tmp_path)
    assert (await service.async_get(task.id, host.id)).state == "unchecked"
    with pytest.raises(ValueError, match="Check task"):
        await service.async_assign(task.id, host.id, enabled=True)
    with pytest.raises(ValueError, match="not assigned"):
        await service.async_require(task.id, host.id)
    assert (await service.async_check(task.id, host.id)).state == "suitable"
    await service.async_assign(task.id, host.id, enabled=True)
    assert (await tasks.async_get(task.id)).host_ids == (host.id,)
    assert (await service.async_require(task.id, host.id, fresh=True))[0].id == task.id
    await service.async_assign(task.id, host.id, enabled=False)
    with pytest.raises(ValueError, match="disabled"):
        await service.async_require(task.id, host.id)
    await service.async_assign(task.id, host.id, enabled=True)
    await hosts.async_patch(host.id, HostPatch(port=2222))
    assert (await service.async_get(task.id, host.id)).state == "unchecked"
    with pytest.raises(ValueError, match="successful current"):
        await service.async_require(task.id, host.id)
    await service.async_check(task.id, host.id)
    await tasks.async_patch(
        task.id, CustomTaskPatch(requirements=TaskRequirements(programs=("curl",)))
    )
    assert (await service.async_get(task.id, host.id)).state == "unchecked"
    await service.async_check(task.id, host.id)
    with patch("backend.homelab_backend.task_compatibility.datetime") as clock:
        clock.now.return_value = datetime.now(UTC) + timedelta(hours=24)
        assert (await service.async_get(task.id, host.id)).state == "unchecked"
    # A future result is not accepted either.
    with patch("backend.homelab_backend.task_compatibility.datetime") as clock:
        clock.now.return_value = datetime.now(UTC) - timedelta(hours=1)
        assert (await service.async_get(task.id, host.id)).state == "unchecked"
    await service.async_unassign(task.id, host.id)
    assert not (await service.async_get(task.id, host.id)).assigned
    with pytest.raises(KeyError):
        await service.async_get(uuid4(), host.id)
    assert database is not None
    assert executor is not None


async def test_incompatible_dependencies_and_safe_probe_failure(tmp_path: Path) -> None:
    _, _, tasks, executor, service, host, task = await _services(tmp_path)
    await tasks.async_patch(
        task.id,
        CustomTaskPatch(
            requirements=TaskRequirements(
                distributions=("ubuntu",), versions=("24.04",)
            )
        ),
    )
    with patch.object(
        executor,
        "async_probe",
        AsyncMock(
            return_value=ProbeFacts(
                distribution="debian",
                version="12",
                missing_programs=["curl"],
                missing_packages=["curl"],
            )
        ),
    ):
        result = await service.async_check(task.id, host.id)
    assert result.state == "unsuitable"
    assert len(result.reasons) == 4
    for error in [
        AutomationExecutionError("synthetic_failure", "private output"),
        TimeoutError(),
    ]:
        with patch.object(executor, "async_probe", AsyncMock(side_effect=error)):
            result = await service.async_check(task.id, host.id)
        assert result.state == "failed"
        assert "private output" not in result.model_dump_json()


async def test_worker_rechecks_assignment_and_privileges_before_execution(
    tmp_path: Path,
) -> None:
    db, hosts, tasks, executor, service, host, task = await _services(tmp_path)
    await service.async_check(task.id, host.id)
    await service.async_assign(task.id, host.id, enabled=True)
    repository = JobRepository(db)
    manager = JobManager(repository, hosts, tasks, executor, compatibility=service)
    job = await manager.async_enqueue_custom(task.id, host.id)
    await service.async_assign(task.id, host.id, enabled=False)
    with patch.object(executor, "async_execute_custom", AsyncMock()) as execute:
        await manager._async_run(job.id)
        execute.assert_not_awaited()
    assert (
        await repository.async_get(job.id)
    ).error_code == "custom_task_not_permitted"
    await service.async_assign(task.id, host.id, enabled=True)
    with (
        patch.object(
            executor,
            "async_probe",
            AsyncMock(side_effect=AutomationExecutionError("sudo_unavailable", "")),
        ),
        pytest.raises(ValueError, match="successful current"),
    ):
        await service.async_require(task.id, host.id, fresh=True)

    # Disable during a probe: the follow-up read must block execution.
    async def disable_during_probe(*_args):
        await tasks.async_patch(task.id, CustomTaskPatch(enabled=False))
        return ProbeFacts(
            distribution="debian",
            version="12",
            missing_programs=[],
            missing_packages=[],
        )

    with (
        patch.object(executor, "async_probe", disable_during_probe),
        pytest.raises(ValueError, match="disabled"),
    ):
        await service.async_require(task.id, host.id, fresh=True)


async def test_dashboard_aggregates_beyond_recent_job_limit_and_pages(
    tmp_path: Path,
) -> None:
    db, _, _, _, _, host, _ = await _services(tmp_path)
    repository = JobRepository(db)
    first = await repository.async_create(JobAction.CHECK_UPDATES, host.id)
    await repository.async_finish(
        first.id, state=JobState.FAILED, output="synthetic", truncated=False
    )
    for _ in range(105):
        await repository.async_create(JobAction.CHECK_UPDATES, host.id)
    summary = await DashboardService(db, repository).async_summary()
    assert summary.queued_jobs == 105
    assert len(summary.recent_jobs) == 5
    assert summary.last_failed_job.id == first.id
    assert len(summary.history) == 7
    assert sum(sum(day.counts.values()) for day in summary.history) == 106
    assert summary.recent_completions[0].id == first.id
    assert await repository.async_count(host_id=host.id, state=JobState.QUEUED) == 105
    assert (
        len(
            await repository.async_list(
                limit=25, offset=100, host_id=host.id, state=JobState.QUEUED
            )
        )
        == 5
    )
    assert await repository.async_count(host_id=uuid4()) == 0


async def test_migration_preserves_legacy_tasks_hosts_and_jobs(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    host_id, task_id, job_id = map(str, (uuid4(), uuid4(), uuid4()))
    now = datetime.now(UTC).isoformat()
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(
            "CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY)"
        )
        for index, migration in enumerate(_MIGRATIONS[:-1], 1):
            connection.executescript(migration)
            connection.execute("INSERT INTO schema_migrations VALUES (?)", (index,))
        connection.execute(
            "INSERT INTO hosts(id,name,address,port,username,package_provider,"
            "created_at,updated_at) VALUES (?,?,?,22,?,'debian_apt',?,?)",
            (host_id, "Node 01", "node-01.example.invalid", "automation", now, now),
        )
        connection.execute(
            "INSERT INTO custom_tasks VALUES (?,?,?,'command',?,NULL,1,?,?)",
            (task_id, "Legacy", "", '["uptime"]', now, now),
        )
        connection.execute(
            "INSERT INTO jobs(id,action,host_id,state,created_at) "
            "VALUES (?,'custom_task',?,'success',?)",
            (job_id, host_id, now),
        )
    database = Database(path)
    await database.async_migrate()
    await database.async_migrate()
    tasks = CustomTaskRepository(database, allow_shell=False)
    assert (await tasks.async_get(UUID(task_id))).host_ids == (UUID(host_id),)
    service = TaskCompatibilityService(
        database, tasks, HostRepository(database), FakeExecutor()
    )
    result = await service.async_get(UUID(task_id), UUID(host_id))
    assert result.assigned
    assert result.enabled
    assert result.state == "unchecked"
    assert (await JobRepository(database).async_get(UUID(job_id))).state == "success"
    new_host = await HostRepository(database).async_create(
        HostCreate(
            name="Node 02", address="node-02.example.invalid", username="automation"
        )
    )
    assert not (await service.async_get(UUID(task_id), new_host.id)).assigned


@pytest.mark.parametrize("prefix", ["/api/v1", "/ui-api"])
def test_assignment_api_auth_csrf_and_direct_execution_guard(
    tmp_path: Path, prefix: str
) -> None:
    with _client(tmp_path, FakeExecutor(), ingress_mode=True) as client:
        host = _create_host(client)
        task = client.post(
            "/api/v1/custom-tasks",
            headers=AUTH,
            json={"name": "Uptime", "argv": ["uptime"]},
        ).json()
        assert (
            client.patch(
                f"/api/v1/custom-tasks/{task['id']}",
                headers=AUTH,
                json={"requirements": None},
            ).status_code
            == 422
        )
        root = f"{prefix}/hosts/{host['id']}/tasks/{task['id']}"
        headers = AUTH if prefix == "/api/v1" else {"X-CSRF-Token": _csrf(client)}
        assert (
            client.put(
                root + "/assignment", headers=headers, json={"enabled": True}
            ).status_code
            == 409
        )
        assert (
            client.post(root + "/check", headers=headers).json()["state"] == "suitable"
        )
        assert client.put(
            root + "/assignment", headers=headers, json={"enabled": True}
        ).json()["enabled"]
        assert client.get(
            f"{prefix}/hosts/{host['id']}/task-compatibility", headers=headers
        ).json()[0]["assigned"]
        if prefix == "/ui-api":
            assert client.post(root + "/check").status_code == 403
            assert (
                client.put(root + "/assignment", json={"enabled": False}).status_code
                == 403
            )
            assert client.delete(root + "/assignment").status_code == 403
        execution = f"{prefix}/hosts/{host['id']}/" + (
            f"actions/tasks/{task['id']}"
            if prefix == "/api/v1"
            else f"tasks/{task['id']}"
        )
        job = client.post(execution, headers=headers)
        assert job.status_code == 202
        assert _terminal_job(client, job.json()["id"])["state"] == "success"
        assert client.get(f"{prefix}/dashboard", headers=headers).json()["hosts"] == 1
        assert (
            client.get(
                f"{prefix}/jobs/page?host_id={host['id']}&state=success&limit=1",
                headers=headers,
            ).json()["total"]
            == 1
        )
        assert (
            client.get(f"{prefix}/jobs/page?limit=101", headers=headers).status_code
            == 422
        )
        assert client.delete(root + "/assignment", headers=headers).status_code == 204
        assert client.post(execution, headers=headers).status_code == 409
        missing = root.replace(task["id"], str(uuid4()))
        assert client.post(missing + "/check", headers=headers).status_code == 404
        assert (
            client.put(
                missing + "/assignment", headers=headers, json={"enabled": True}
            ).status_code
            == 404
        )
        assert (
            client.delete(missing + "/assignment", headers=headers).status_code == 404
        )
        assert (
            client.get(
                f"{prefix}/hosts/{uuid4()}/task-compatibility", headers=headers
            ).status_code
            == 404
        )


def test_onboarding_api_and_import_envelope(tmp_path: Path) -> None:
    with _client(tmp_path, FakeExecutor()) as client:
        assert (
            client.get(
                "/ui-api/onboarding?system=debian&username=automation"
            ).status_code
            == 401
        )
    with _client(tmp_path, FakeExecutor(), ingress_mode=True) as client:
        for system in ("debian", "ubuntu"):
            result = client.get(
                f"/ui-api/onboarding?system={system}&username=automation&port=2222"
            )
            assert result.status_code == 200
            command = result.json()["command"]
            assert "sudo python3" in command
            assert "HLC_HOST_BEGIN" in command
            assert "private" not in command
        for query in [
            "system=fedora&username=automation",
            "system=debian&username=root",
            "system=debian&username=bad;user",
            "system=debian&username=automation&port=0",
        ]:
            assert client.get("/ui-api/onboarding?" + query).status_code == 422


async def test_ansible_probe_validates_fixed_script_output(tmp_path: Path) -> None:
    _, _, _, _, _, host, task = await _services(tmp_path)
    executor = AnsibleExecutor(tmp_path / "key", tmp_path / "known_hosts")
    facts = {
        "distribution": "debian",
        "version": "12",
        "missing_programs": [],
        "missing_packages": [],
    }
    with patch.object(
        executor,
        "_async_module",
        AsyncMock(return_value=({"stdout": json.dumps(facts)}, "")),
    ) as module:
        assert (await executor.async_probe(task, host)).distribution == "debian"
        argv = json.loads(module.call_args.args[2])["argv"]
        assert argv[:2] == ["python3", "-c"]
        assert argv[2] == _PROBE_SCRIPT
        assert json.loads(argv[3])["programs"] == ["uptime"]
    with (
        patch.object(
            executor,
            "_async_module",
            AsyncMock(return_value=({"stdout": "not json"}, "")),
        ),
        pytest.raises(AutomationExecutionError, match="invalid_probe_output"),
    ):
        await executor.async_probe(task, host)


@pytest.mark.parametrize("system", ["debian", "ubuntu"])
@pytest.mark.parametrize("existing_account", [True, False])
def test_setup_template_is_idempotent_and_only_touches_synthetic_account(
    tmp_path: Path, system: str, capsys, existing_account: bool
) -> None:
    key = "ssh-ed25519 AAAA synthetic"
    command = setup_command(system, "automation", 2222, key).command
    script = command.split("\n", 1)[1].rsplit("\n", 1)[0]
    account = SimpleNamespace(
        pw_dir=str(tmp_path), pw_uid=os.getuid(), pw_gid=os.getgid()
    )
    real_open = builtins.open

    def fake_open(path, *args, **kwargs):
        if path == "/etc/os-release":
            from io import StringIO

            return StringIO(f"ID={system}\n")
        return real_open(path, *args, **kwargs)

    with (
        patch("builtins.open", fake_open),
        patch("os.geteuid", return_value=0),
        patch(
            "pwd.getpwnam",
            side_effect=[account, account]
            if existing_account
            else [KeyError(), account, account],
        ),
        patch(
            "subprocess.check_output",
            return_value="node-01.example.invalid node-02.example.invalid",
        ),
        patch("socket.gethostname", return_value="node-01"),
        patch("subprocess.run") as run,
    ):
        exec(compile(script, "<synthetic-setup>", "exec"), {})
        exec(compile(script, "<synthetic-setup>", "exec"), {})
        if existing_account:
            run.assert_not_called()
        else:
            run.assert_called_once_with(
                ["useradd", "--create-home", "--shell", "/bin/sh", "--", "automation"],
                check=True,
            )
    assert (tmp_path / ".ssh/authorized_keys").read_text() == key + "\n"
    assert (tmp_path / ".ssh/authorized_keys").stat().st_mode & 0o777 == 0o600
    output = capsys.readouterr().out
    data = json.loads(output.split("HLC_HOST_BEGIN\n")[1].split("\nHLC_HOST_END")[0])
    assert data["version"] == 1
    assert data["port"] == 2222
    assert len(data["addresses"]) == 2


async def test_changes_during_probe_cannot_authorize_new_inputs(tmp_path: Path) -> None:
    _, hosts, _, executor, service, host, task = await _services(tmp_path)
    await service.async_check(task.id, host.id)
    await service.async_assign(task.id, host.id, enabled=True)

    async def edit_during_probe(*_args):
        await hosts.async_patch(host.id, HostPatch(port=2222))
        return ProbeFacts(
            distribution="debian",
            version="12",
            missing_programs=[],
            missing_packages=[],
        )

    with (
        patch.object(executor, "async_probe", edit_during_probe),
        pytest.raises(ValueError, match="changed during"),
    ):
        await service.async_require(task.id, host.id, fresh=True)
    assert (await service.async_get(task.id, host.id)).state == "unchecked"
    await hosts.async_patch(host.id, HostPatch(port=22))
    assert (await service.async_get(task.id, host.id)).state == "unchecked"


@pytest.mark.parametrize("dpkg_present", [True, False])
def test_fixed_probe_reads_os_and_dependency_state_only(
    dpkg_present: bool, capsys
) -> None:
    """Exercise the exact remote script with simulated tools and package queries."""
    from io import StringIO

    requirement = {
        "programs": ["uptime", "missing-tool"],
        "packages": ["curl", "missing-package"],
    }

    def which(name):
        return (
            "/usr/bin/" + name
            if name == "uptime" or (name == "dpkg-query" and dpkg_present)
            else None
        )

    def package_query(argv, **kwargs):
        assert argv[:5] == ["dpkg-query", "-W", "-f=${Status}", "--", argv[4]]
        assert kwargs["timeout"] == 5
        installed = argv[-1] == "curl"
        return SimpleNamespace(
            returncode=0 if installed else 1,
            stdout="install ok installed" if installed else "",
        )

    with (
        patch("builtins.open", return_value=StringIO('ID=debian\nVERSION_ID="12"\n')),
        patch("sys.argv", ["probe", json.dumps(requirement)]),
        patch("shutil.which", which),
        patch("subprocess.run", package_query),
    ):
        exec(compile(_PROBE_SCRIPT, "<synthetic-probe>", "exec"), {})
    facts = ProbeFacts.model_validate_json(capsys.readouterr().out)
    assert facts.distribution == "debian"
    assert facts.version == "12"
    assert facts.missing_programs == ("missing-tool",)
    assert facts.missing_packages == (
        ("missing-package",) if dpkg_present else ("curl", "missing-package")
    )


async def test_worker_redacts_the_connection_it_actually_used(tmp_path: Path) -> None:
    db, hosts, tasks, executor, service, host, task = await _services(tmp_path)
    await service.async_check(task.id, host.id)
    await service.async_assign(task.id, host.id, enabled=True)
    repository = JobRepository(db)
    job = await repository.async_create(
        JobAction.CUSTOM_TASK, host.id, custom_task_id=task.id
    )
    await hosts.async_patch(host.id, HostPatch(address="node-02.example.invalid"))
    original_get = hosts.async_get
    reads = 0

    async def changed_host(host_id):
        nonlocal reads
        reads += 1
        return host if reads == 1 else await original_get(host_id)

    manager = JobManager(repository, hosts, tasks, executor, compatibility=service)
    with patch.object(hosts, "async_get", changed_host):
        await manager._async_run(job.id)
    log = await repository.async_log(job.id)
    assert "node-02.example.invalid" not in log.output
    assert "[redacted]" in log.output
