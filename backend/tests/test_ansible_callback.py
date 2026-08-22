"""Private Ansible callback contract tests without starting Ansible."""

import json
from unittest.mock import MagicMock

import pytest

from backend.homelab_backend.ansible_plugins.homelab_json import CallbackModule
from backend.homelab_backend.ansible_result import RESULT_PREFIX


@pytest.mark.parametrize(
    ("method_name", "event"),
    [
        ("v2_runner_on_ok", "ok"),
        ("v2_runner_on_failed", "failed"),
        ("v2_runner_on_unreachable", "unreachable"),
    ],
)
def test_callback_emits_one_machine_readable_envelope(
    method_name: str, event: str
) -> None:
    """Warnings are handled separately and the result stays structured."""
    callback = CallbackModule()
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
