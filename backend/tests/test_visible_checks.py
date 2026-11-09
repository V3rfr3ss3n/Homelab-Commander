"""Visible-only status checks and operator-selected website link contracts."""

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from backend.homelab_backend.jobs import JobManager, JobRepository
from backend.homelab_backend.models import HostWebsite, JobAction, JobState
from backend.homelab_backend.visible_checks import HostCheckPreferences, VisibleChecks
from backend.tests.test_backend_api import (
    AUTH,
    FakeExecutor,
    _client,
    _create_host,
    _csrf,
    _terminal_job,
)
from backend.tests.test_dashboard import _services


async def test_visible_checks_cooldown_active_work_and_preference(
    tmp_path: Path,
) -> None:
    db, hosts, tasks, executor, _, host, _ = await _services(tmp_path)
    repository = JobRepository(db)
    manager = JobManager(repository, hosts, tasks, executor)
    service = VisibleChecks(db, hosts, manager)
    assert (await service.async_preferences()).enabled
    # Simultaneous tabs share one atomic claim even before execution begins.
    results = await asyncio.gather(service.async_check(), service.async_check())
    assert sum(map(len, results)) == 1
    assert (await repository.async_list())[0].action == JobAction.CHECK_UPDATES
    assert await service.async_check() == ()
    job = (await repository.async_list())[0]
    await repository.async_finish(
        job.id, state=JobState.FAILED, output="", truncated=False
    )
    assert await service.async_check() == ()  # failed checks also respect cooldown
    await db.async_execute("DELETE FROM ui_auto_checks")
    now = datetime.now(UTC)
    await db.async_execute("UPDATE hosts SET checked_at=?", (now.isoformat(),))
    assert await service.async_check() == ()
    await db.async_execute("UPDATE hosts SET checked_at=NULL")
    await service.async_update(HostCheckPreferences(enabled=False))
    assert await service.async_check() == ()
    assert not await service._claim(host.id, now)
    await service.async_update(HostCheckPreferences(enabled=True))
    assert not await service._claim(uuid4(), now)
    # A request selected just before host deletion must not attempt execution.
    with patch.object(
        manager, "async_enqueue", AsyncMock(side_effect=KeyError("removed"))
    ):
        assert await service.async_check() == ()
    await db.async_execute(
        "UPDATE ui_auto_checks SET requested_at=?",
        ((now - timedelta(minutes=6)).isoformat(),),
    )
    assert len(await service.async_check()) == 1


def test_preferences_and_visible_check_api_authentication(tmp_path: Path) -> None:
    with _client(tmp_path, FakeExecutor(), ingress_mode=True) as client:
        host = _create_host(client)
        csrf = {"X-CSRF-Token": _csrf(client)}
        assert client.get("/ui-api/preferences/host-checks").json() == {"enabled": True}
        assert (
            client.patch(
                "/ui-api/preferences/host-checks", json={"enabled": False}
            ).status_code
            == 403
        )
        assert client.post("/ui-api/actions/check-visible").status_code == 403
        jobs = client.post("/ui-api/actions/check-visible", headers=csrf).json()
        assert len(jobs) == 1
        assert jobs[0]["host_id"] == host["id"]
        assert _terminal_job(client, jobs[0]["id"])["state"] == "success"
        assert client.post("/ui-api/actions/check-visible", headers=csrf).json() == []
        assert client.patch(
            "/ui-api/preferences/host-checks", headers=csrf, json={"enabled": False}
        ).json() == {"enabled": False}
        assert client.post("/ui-api/actions/check-visible", headers=csrf).json() == []
    with _client(tmp_path, FakeExecutor(), ingress_mode=True) as client:
        assert client.get("/ui-api/preferences/host-checks").json() == {
            "enabled": False
        }
    with _client(tmp_path, FakeExecutor()) as client:
        assert client.get("/ui-api/preferences/host-checks").status_code == 401


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "file:///tmp/demo",
        "https://user:password@service.example.invalid",
        "https://user@service.example.invalid",
        "not a URL",
    ],
)
def test_websites_reject_unsafe_or_credential_links(url: str) -> None:
    with pytest.raises(ValueError, match="validation error"):
        HostWebsite(name="Dashboard", url=url)


def test_host_website_crud_preserves_id_and_other_fields(tmp_path: Path) -> None:
    with _client(tmp_path, FakeExecutor()) as client:
        host = _create_host(client)
        sites = [{"name": "Dashboard", "url": "https://service.example.invalid/ui"}]
        changed = client.patch(
            f"/api/v1/hosts/{host['id']}", headers=AUTH, json={"websites": sites}
        )
        assert changed.status_code == 200
        assert changed.json()["websites"] == sites
        assert changed.json()["id"] == host["id"]
        assert client.get("/api/v1/hosts", headers=AUTH).json()[0]["websites"] == sites
        renamed = client.patch(
            f"/api/v1/hosts/{host['id']}", headers=AUTH, json={"name": "Renamed"}
        ).json()
        assert renamed["websites"] == sites
        assert renamed["address"] == host["address"]
        assert (
            client.patch(
                f"/api/v1/hosts/{host['id']}",
                headers=AUTH,
                json={"websites": sites * 13},
            ).status_code
            == 422
        )
        assert (
            client.patch(
                f"/api/v1/hosts/{host['id']}", headers=AUTH, json={"websites": []}
            ).json()["websites"]
            == []
        )
        created = client.post(
            "/api/v1/hosts",
            headers=AUTH,
            json={
                "name": "Node 02",
                "address": "node-02.example.invalid",
                "username": "automation",
                "websites": sites,
            },
        ).json()
        assert created["websites"] == sites


async def test_resolved_failure_leaves_attention_but_remains_in_history(
    tmp_path: Path,
) -> None:
    db, _, _, _, _, host, _ = await _services(tmp_path)
    repository = JobRepository(db)
    failure = await repository.async_create(JobAction.CHECK_UPDATES, host.id)
    await repository.async_finish(
        failure.id, state=JobState.FAILED, output="", truncated=False
    )
    assert (await repository.async_unresolved_failure()).id == failure.id
    success = await repository.async_create(JobAction.CHECK_UPDATES, host.id)
    await repository.async_finish(
        success.id, state=JobState.SUCCESS, output="", truncated=False
    )
    assert await repository.async_unresolved_failure() is None
    assert len(await repository.async_list(state=JobState.FAILED)) == 1
