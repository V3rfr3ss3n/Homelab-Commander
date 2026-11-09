"""Run rendered setup only against synthetic accounts and redirected filesystem I/O."""

import json
import os
import subprocess
from contextlib import contextmanager
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from backend.homelab_backend.onboarding import SetupOptions, setup_command
from backend.tests.test_backend_api import FakeExecutor, _client

KEY = "ssh-ed25519 AAAA synthetic"


@contextmanager
def simulated_host(tmp_path: Path, *, missing: bool = False, system: str = "debian"):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    rules = tmp_path / "sudoers.d"
    rules.mkdir(exist_ok=True)
    account = SimpleNamespace(
        pw_dir=str(home), pw_uid=max(1, os.getuid()), pw_gid=os.getgid()
    )
    real_open, real_fstat = os.open, os.fstat

    def host_open(path, *args, **kwargs):
        if path == "/etc/sudoers.d":
            path = str(rules)
        if isinstance(path, str) and path.startswith("/etc/"):
            raise AssertionError("Unexpected real system path")
        return real_open(path, *args, **kwargs)

    def release_open(path, *args, **kwargs):
        assert path == "/etc/os-release"
        return StringIO(f"ID={system}\n")

    def stat(descriptor):
        result = real_fstat(descriptor)
        return SimpleNamespace(
            st_mode=result.st_mode, st_nlink=result.st_nlink, st_uid=0
        )

    with (
        patch("builtins.open", release_open),
        patch("os.open", host_open),
        patch("os.fstat", stat),
        patch("os.fchown"),
        patch("os.geteuid", return_value=0),
        patch(
            "pwd.getpwnam",
            side_effect=KeyError if missing else None,
            return_value=account,
        ),
        patch("subprocess.run") as run,
        patch("subprocess.check_output", return_value="node-01.example.invalid"),
        patch("socket.gethostname", return_value="node-01"),
    ):
        yield home, rules, run


def execute(options: SetupOptions) -> None:
    command = setup_command("debian", "automation", 2222, KEY, options).command
    script = command.split("HLC_SETUP'\n", 1)[1].rsplit("\n", 1)[0]
    exec(compile(script, "<isolated-setup>", "exec"), {})


def test_explicit_sudo_and_update_are_idempotent_and_preserve_other_rules(tmp_path):
    with simulated_host(tmp_path) as (home, rules, run):
        unrelated = rules / "unrelated"
        unrelated.write_text("# independent operator rule\n")
        (home / ".ssh").mkdir()
        (home / ".ssh/authorized_keys").write_text("ssh-ed25519 OTHER operator\n")
        options = SetupOptions(sudo="full", source="192.0.2.0/24")
        execute(options)
        execute(options)
        rule = rules / "homelab-commander-automation"
        assert rule.read_text().endswith("automation ALL=(root) NOPASSWD: ALL\n")
        assert rule.stat().st_mode & 0o777 == 0o440
        keys = home / ".ssh/authorized_keys"
        assert keys.read_text().count(KEY) == 1
        assert 'from="192.0.2.0/24"' in keys.read_text()
        assert "no-port-forwarding" in keys.read_text()
        assert all(call.args[0][0] == "visudo" for call in run.call_args_list)
        execute(SetupOptions(mode="update", shell="/bin/bash", restricted_key=False))
        assert not rule.exists()
        assert unrelated.read_text() == "# independent operator rule\n"
        assert keys.read_text() == "ssh-ed25519 OTHER operator\n" + KEY + "\n"
        assert run.call_args.args[0] == [
            "usermod",
            "--shell",
            "/bin/bash",
            "--",
            "automation",
        ]


def test_setup_refuses_foreign_rules_and_symlinks(tmp_path):
    with simulated_host(tmp_path) as (_, rules, _):
        target = rules / "homelab-commander-automation"
        target.write_text("# operator-owned\n")
        with pytest.raises(SystemExit, match="unmanaged"):
            execute(SetupOptions(sudo="full"))
        assert target.read_text() == "# operator-owned\n"
        target.unlink()
        outside = tmp_path / "outside"
        outside.write_text("untouched")
        target.symlink_to(outside)
        with pytest.raises(OSError, match="Too many levels"):
            execute(SetupOptions(sudo="full"))
        assert outside.read_text() == "untouched"


def test_invalid_sudo_candidate_is_not_installed(tmp_path):
    with simulated_host(tmp_path) as (_, rules, run):
        run.side_effect = subprocess.CalledProcessError(1, "synthetic-visudo")
        with pytest.raises(subprocess.CalledProcessError):
            execute(SetupOptions(sudo="full"))
        assert list(rules.iterdir()) == []


def test_update_requires_account_and_matching_system(tmp_path):
    with (
        simulated_host(tmp_path, missing=True),
        pytest.raises(SystemExit, match="Account does not exist"),
    ):
        execute(SetupOptions(mode="update"))
    with (
        simulated_host(tmp_path, system="ubuntu"),
        pytest.raises(SystemExit, match="does not match"),
    ):
        execute(SetupOptions())


@pytest.mark.parametrize("source", ["192.0.2.1", "2001:db8::/64", ""])
def test_setup_source_is_declarative(source):
    assert SetupOptions(source=source).source == source
    with pytest.raises(ValidationError):
        SetupOptions(source='192.0.2.1"; arbitrary')


def test_script_options_api_validate_before_rendering(tmp_path):
    with _client(tmp_path, FakeExecutor(), ingress_mode=True) as client:
        endpoint = "/ui-api/onboarding?system=debian&username=automation"
        for extra in [
            "source=invalid",
            "shell=/bin/evil",
            "mode=remove",
            "sudo=arbitrary",
        ]:
            assert client.get(endpoint + "&" + extra).status_code == 422
        result = client.get(endpoint + "&mode=update&sudo=full&source=192.0.2.0/24")
        assert result.status_code == 200
        command = result.json()["command"]
        assert "192.0.2.0/24" in command
        config = json.loads(
            command.split("config = json.loads(", 1)[1].split("\n", 1)[0][1:-2]
        )
        assert config["mode"] == "update"
        assert config["sudo"] == "full"
