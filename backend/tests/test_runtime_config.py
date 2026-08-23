"""Environment and container bootstrap validation."""

import json
import os
from pathlib import Path
from unittest.mock import Mock

import pytest

from backend.homelab_backend import __main__ as backend_main
from backend.homelab_backend import container_entrypoint
from backend.homelab_backend.config import Settings


def test_settings_load_validated_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HUL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HUL_API_TOKEN", "x" * 32)
    monkeypatch.setenv("HUL_LOG_LEVEL", "warning")
    monkeypatch.setenv("HUL_ALLOW_SHELL_TASKS", "true")
    monkeypatch.setenv("HUL_INGRESS_MODE", "true")

    settings = Settings.from_env()

    assert settings.data_dir == tmp_path
    assert settings.log_level == "WARNING"
    assert settings.allow_shell_tasks
    assert settings.ingress_mode
    assert settings.database_path == tmp_path / "homelab_updates.db"
    assert settings.private_key_path == tmp_path / "ssh/id_ed25519"
    assert settings.known_hosts_path == tmp_path / "ssh/known_hosts"


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        ({"HUL_API_TOKEN": "short"}, "at least 32"),
        ({"HUL_API_TOKEN": "x" * 32, "HUL_LOG_LEVEL": "verbose"}, "LOG_LEVEL"),
        (
            {"HUL_API_TOKEN": "x" * 32, "HUL_ALLOW_SHELL_TASKS": "yes"},
            "ALLOW_SHELL",
        ),
        (
            {"HUL_API_TOKEN": "x" * 32, "HUL_INGRESS_MODE": "yes"},
            "INGRESS_MODE",
        ),
    ],
)
def test_settings_reject_invalid_environment(
    monkeypatch: pytest.MonkeyPatch,
    environment: dict[str, str],
    message: str,
) -> None:
    for key in (
        "HUL_API_TOKEN",
        "HUL_LOG_LEVEL",
        "HUL_ALLOW_SHELL_TASKS",
        "HUL_INGRESS_MODE",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match=message):
        Settings.from_env()


def test_container_entrypoint_loads_options_and_executes_unprivileged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    options = tmp_path / "options.json"
    options.write_text(
        json.dumps({
            "api_token": "z" * 32,
            "log_level": "INFO",
            "allow_shell_tasks": False,
            "ignored": 1,
        })
    )
    monkeypatch.setenv("HUL_OPTIONS_PATH", str(options))
    monkeypatch.setenv("HUL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(os, "geteuid", lambda: 10001)
    execute = Mock(side_effect=RuntimeError("exec intercepted"))
    monkeypatch.setattr(os, "execvp", execute)

    with pytest.raises(RuntimeError, match="intercepted"):
        container_entrypoint.main()

    assert os.environ["HUL_API_TOKEN"] == "z" * 32
    assert os.environ["HUL_ALLOW_SHELL_TASKS"] == "false"
    assert os.environ["HUL_INGRESS_MODE"] == "true"
    execute.assert_called_once_with(
        "homelab-updates-backend", ["homelab-updates-backend"]
    )


def test_container_entrypoint_drops_root_and_chowns_fixed_data_tree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "state").write_text("synthetic")
    monkeypatch.setenv("HUL_OPTIONS_PATH", str(tmp_path / "missing.json"))
    monkeypatch.setenv("HUL_DATA_DIR", str(data_dir))
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    chown = Mock()
    monkeypatch.setattr(os, "chown", chown)
    setgroups = Mock()
    setgid = Mock()
    setuid = Mock()
    monkeypatch.setattr(os, "setgroups", setgroups)
    monkeypatch.setattr(os, "setgid", setgid)
    monkeypatch.setattr(os, "setuid", setuid)
    monkeypatch.setattr(os, "execvp", Mock(side_effect=RuntimeError("intercepted")))

    with pytest.raises(RuntimeError, match="intercepted"):
        container_entrypoint.main()

    assert chown.call_count >= 2
    setgroups.assert_called_once_with([])
    setgid.assert_called_once_with(10001)
    setuid.assert_called_once_with(10001)


def test_container_entrypoint_rejects_non_object_options(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    options = tmp_path / "options.json"
    options.write_text("[]")
    monkeypatch.setenv("HUL_OPTIONS_PATH", str(options))
    with pytest.raises(ValueError, match="JSON object"):
        container_entrypoint.main()


def test_uvicorn_main_uses_factory_and_safe_listener() -> None:
    with pytest.MonkeyPatch.context() as monkeypatch:
        run = Mock()
        monkeypatch.setattr(backend_main.uvicorn, "run", run)
        backend_main.main()
    run.assert_called_once_with(
        "homelab_backend.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=8099,
        proxy_headers=True,
    )


def test_container_option_ignores_unsupported_value_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Supervisor option parsing accepts only strings and booleans."""
    monkeypatch.delenv("HUL_SYNTHETIC", raising=False)
    container_entrypoint._set_option({"value": 1}, "value", "HUL_SYNTHETIC")
    assert "HUL_SYNTHETIC" not in os.environ
