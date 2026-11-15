"""Private Ansible callback contract tests without starting Ansible."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.homelab_backend.ansible_result import RESULT_PREFIX


@pytest.fixture
def callback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> object:
    config = tmp_path / "ansible.cfg"
    config.write_text("[defaults]\n")
    monkeypatch.setenv("ANSIBLE_CONFIG", str(config))
    monkeypatch.setenv("ANSIBLE_HOME", str(tmp_path / "ansible"))
    monkeypatch.setenv("ANSIBLE_LOCAL_TEMP", str(tmp_path / "tmp"))
    from backend.homelab_backend.ansible_plugins.homelab_json import CallbackModule

    return CallbackModule()


@pytest.mark.parametrize(
    ("method_name", "event"),
    [
        ("v2_runner_on_ok", "ok"),
        ("v2_runner_on_failed", "failed"),
        ("v2_runner_on_unreachable", "unreachable"),
    ],
)
def test_callback_emits_one_machine_readable_envelope(
    method_name: str, event: str, callback: object
) -> None:
    """Warnings are handled separately and the result stays structured."""
    callback._display = MagicMock()  # type: ignore[assignment]
    callback._handle_warnings_and_exception = MagicMock()  # type: ignore[method-assign]
    callback._dump_results = MagicMock(  # type: ignore[method-assign]
        return_value='{"changed":false,"rc":0}'
    )
    result = MagicMock()
    result.result = {"changed": False, "rc": 0}

    method = getattr(callback, method_name)
    method(result)

    callback._handle_warnings_and_exception.assert_called_once_with(result)
    line = callback._display.display.call_args.args[0]
    assert line.startswith(RESULT_PREFIX)
    envelope = json.loads(line.removeprefix(RESULT_PREFIX))
    assert envelope == {
        "event": event,
        "result": {"changed": False, "rc": 0},
    }


@pytest.mark.parametrize(
    "method", ["v2_runner_on_ok", "v2_runner_on_failed", "v2_runner_on_unreachable"]
)
def test_callback_never_serializes_no_log_payload(
    callback: object, method: str
) -> None:
    callback._display = MagicMock()
    callback._dump_results = MagicMock()
    callback._handle_warnings_and_exception = MagicMock()
    result = MagicMock()
    result.result = {"_ansible_no_log": True, "msg": "synthetic-private-secret"}
    getattr(callback, method)(result)
    callback._dump_results.assert_not_called()
    callback._handle_warnings_and_exception.assert_not_called()
    line = callback._display.display.call_args.args[0]
    assert "synthetic-private-secret" not in line
    assert json.loads(line.removeprefix(RESULT_PREFIX))["result"] == {"censored": True}
