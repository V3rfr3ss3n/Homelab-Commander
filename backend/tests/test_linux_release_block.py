"""Native-package release cases with injected command and process boundaries."""

import json
import subprocess
from unittest.mock import Mock

import pytest

from backend.homelab_backend.execution.results import AutomationExecutionError
from backend.homelab_backend.linux.providers.apk import candidates
from backend.homelab_backend.linux.providers.pacman_review import (
    REVIEW_SCRIPT,
    split_review,
)
from backend.homelab_backend.models import JobAction
from backend.tests.test_package_sources import SourcesRunner, auto_host
from backend.tests.test_rpm_providers import executor


class AlpineRunner(SourcesRunner):
    def __init__(self):
        super().__init__()
        self.facts.update(
            ansible_distribution="Alpine",
            ansible_distribution_version="3.23.1",
            ansible_pkg_mgr="apk",
        )
        self.flatpak_present = False
        self.apk_calls = []
        self.pending = {"lib-2": "1.1-r1", "busybox": "1.37.0-r3"}

    async def async_module(self, host, module, arguments=None, **kwargs):
        if module == "ansible.builtin.command":
            native = json.loads(json.loads(arguments)["argv"][3])["argv"]
            if native[0] == "/sbin/apk":
                self.apk_calls.append((native[1:], kwargs["become"]))
                output = ""
                if native[1:] == ["version", "-l", "<"]:
                    output = "Installed:          Available:\n" + "".join(
                        f"{name}-1.0-r0  < {version}\n"
                        for name, version in self.pending.items()
                    )
                if native[1:] == ["upgrade"]:
                    self.pending.clear()
                    self.writes += 1
                return {"stdout": json.dumps({"rc": 0, "stdout": output})}, ""
        return await super().async_module(host, module, arguments, **kwargs)


@pytest.mark.parametrize("policy", ["auto", "apk"])
async def test_alpine_full_upgrade_and_native_refresh(tmp_path, policy):
    runner = AlpineRunner()
    host = auto_host(package_provider=policy)
    run = executor(tmp_path, runner)
    result = await run.async_execute(JobAction.CHECK_UPDATES, host)
    assert result.snapshot.updates == 2
    assert result.snapshot.package_scopes == ("full",)
    assert result.snapshot.security_updates is None
    assert result.snapshot.reboot_required is None
    assert runner.apk_calls == [(["update"], True), (["version", "-l", "<"], False)]
    name = result.snapshot.packages[0].name
    with pytest.raises(AutomationExecutionError, match="package_scope_unsupported"):
        await run.async_execute(JobAction.UPDATE, host, name)
    assert not runner.writes
    final = await run.async_execute(JobAction.UPDATE, host)
    assert final.snapshot.updates == 0
    assert runner.writes == 1
    assert runner.apk_calls[-2:] == [
        (["upgrade"], True),
        (["version", "-l", "<"], False),
    ]


@pytest.mark.parametrize(
    "output",
    [
        "",
        "WARNING: stale",
        "Installed: Available:\nmalformed",
        "Installed: Available:\npkg-1-r0 < 2-r0\npkg-1-r0 < 2-r0",
    ],
)
def test_alpine_inventory_invalid_output_is_never_empty_success(output):
    with pytest.raises(AutomationExecutionError, match="invalid_package_output"):
        candidates(output)


def test_alpine_version_table_keeps_numeric_package_suffix_and_repo_tag():
    (row,) = candidates(
        "Installed:  Available:\nlib-2-1.2_rc1-r0   < 1.2-r1 @testing\n"
    )
    assert row.name == "lib-2"
    assert row.old_version == "1.2_rc1-r0"
    assert row.new_version == "1.2-r1"


@pytest.mark.parametrize(
    "output",
    [
        "missing",
        "HLC_ALPM_PLAN\n",
        "HLC_ALPM_PLAN\nbad\nHLC_ALPM_FOREIGN\n",
        "HLC_ALPM_PLAN\npkg 1\npkg 2\nHLC_ALPM_FOREIGN\n",
    ],
)
def test_alpm_invalid_preview_fails_closed(output):
    with pytest.raises(AutomationExecutionError, match="invalid_package_output"):
        split_review(output)


def test_alpm_commands_use_disposable_db_and_never_apply_transaction(monkeypatch):
    native = Mock(
        side_effect=[Mock(returncode=2), Mock(returncode=0), Mock(returncode=1)]
    )
    monkeypatch.setattr(subprocess, "run", native)
    with pytest.raises(SystemExit) as done:
        exec(REVIEW_SCRIPT, {})
    assert done.value.code == 0
    first, plan, foreign = native.call_args_list
    scratch = first.kwargs["env"]["CHECKUPDATES_DB"]
    assert first.args[0] == ("/usr/bin/checkupdates", "--nocolor")
    assert plan.args[0][1:3] == ("--dbpath", scratch)
    assert "-Sup" in plan.args[0]
    assert foreign.args[0][1:3] == ("--dbpath", scratch)
    assert foreign.args[0][-1] == "-Qm"
    assert all("-Syu" not in call.args[0] for call in native.call_args_list)


def test_dev5_database_and_ssh_identity_survive_dev6_startup(tmp_path):
    import sqlite3
    from contextlib import closing
    from uuid import uuid4

    from fastapi.testclient import TestClient

    from backend.homelab_backend.app import create_app
    from backend.homelab_backend.config import Settings
    from backend.homelab_backend.persistence.migrations import MIGRATIONS
    from backend.homelab_backend.ssh_keys import SshKeyStore
    from backend.tests.test_backend_api import AUTH, TOKEN

    settings = Settings(data_dir=tmp_path, api_token=TOKEN)
    identity, job = str(uuid4()), str(uuid4())
    stamp = "2026-01-01T00:00:00+00:00"
    legacy_rows = json.dumps([
        {
            "name": "demo-editor",
            "old_version": "1",
            "new_version": "2",
            "is_security": True,
        }
    ])
    # These ten SQL revisions are byte-identical to the dev.5 source a1a98d7.
    with closing(sqlite3.connect(settings.database_path)) as db:
        db.execute("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY)")
        for version, migration in enumerate(MIGRATIONS[:10], 1):
            db.executescript(migration)
            db.execute("INSERT INTO schema_migrations VALUES (?)", (version,))
        db.execute(
            "INSERT INTO hosts (id,name,address,port,username,package_provider,"
            "created_at,updated_at,checked_at,updates,security_updates,packages_json) "
            "VALUES (?, 'From dev.5', 'old.example.invalid', 22, 'operator', "
            "'debian_apt', "
            "?, ?, ?, 1, 1, ?)",
            (identity, stamp, stamp, stamp, legacy_rows),
        )
        db.execute(
            "INSERT INTO jobs (id,action,host_id,state,created_at,reviewed_at) "
            "VALUES (?, 'update', ?, 'failed', ?, ?)",
            (job, identity, stamp, stamp),
        )
        db.execute(
            "INSERT INTO job_logs VALUES (?, 'synthetic migration log', 0)", (job,)
        )
        db.execute("UPDATE ui_preferences SET auto_check_enabled=0")
        db.commit()
    SshKeyStore(settings.private_key_path)._ensure()
    before = settings.private_key_path.read_bytes()
    runner = AlpineRunner()
    with TestClient(
        create_app(settings, executor=executor(tmp_path, runner))
    ) as client:
        host = client.get(f"/api/v1/hosts/{identity}", headers=AUTH).json()
        assert host["id"] == identity
        assert host["package_provider"] == "debian_apt"
        assert host["updates"] == 1
        response = client.get(f"/api/v1/hosts/{identity}/packages", headers=AUTH).json()
        assert response["packages"] == json.loads(legacy_rows)
        old_job = client.get(f"/api/v1/jobs/{job}", headers=AUTH).json()
        assert old_job["reviewed_at"] == "2026-01-01T00:00:00Z"
        assert not old_job["needs_review"]
        assert client.get(f"/api/v1/jobs/{job}/log", headers=AUTH).json()["output"] == (
            "synthetic migration log"
        )
    assert settings.private_key_path.read_bytes() == before
    assert not runner.apk_calls
    with closing(sqlite3.connect(settings.database_path)) as db:
        assert db.execute("SELECT MAX(version) FROM schema_migrations").fetchone() == (
            16,
        )
        assert db.execute(
            "SELECT auto_check_enabled FROM ui_preferences"
        ).fetchone() == (0,)


def test_alpm_review_is_available_only_after_a_successful_live_check(tmp_path):
    from fastapi.testclient import TestClient

    from backend.homelab_backend.app import create_app
    from backend.homelab_backend.config import Settings
    from backend.tests.test_backend_api import AUTH, TOKEN, _terminal_job

    runner = SourcesRunner(pacman=True)
    settings = Settings(data_dir=tmp_path, api_token=TOKEN)

    def app():
        return create_app(settings, executor=executor(tmp_path, runner))

    with TestClient(app()) as client:
        host = client.post(
            "/api/v1/hosts",
            headers=AUTH,
            json={
                "name": "Synthetic ALPM",
                "address": "arch.example.invalid",
                "username": "operator",
                "package_provider": "auto",
            },
        ).json()
        root = "/api/v1/hosts/" + host["id"]
        check = client.post(root + "/actions/check-updates", headers=AUTH)
        assert _terminal_job(client, check.json()["id"])["state"] == "success"
        payload = client.get(root + "/packages", headers=AUTH).json()
        assert payload["total"] == 6
        review = payload["pacman_review"]
        assert review["candidate_count"] == 3
        assert review["foreign"] == [{"name": "demo-local", "version": "1.0"}]
        assert client.get(root + "/packages").status_code == 401
        assert runner.writes == 0
    with TestClient(app()) as client:
        payload = client.get(root + "/packages", headers=AUTH).json()
        assert payload["total"] == 6
        assert "pacman_review" not in payload

        checker = client.post(root + "/actions/check-updates", headers=AUTH)
        assert _terminal_job(client, checker.json()["id"])["state"] == "success"
        assert "pacman_review" in client.get(root + "/packages", headers=AUTH).json()
        edit = client.patch(
            root, headers=AUTH, json={"address": "other.example.invalid"}
        )
        assert edit.status_code == 200
        assert (
            "pacman_review" not in client.get(root + "/packages", headers=AUTH).json()
        )
