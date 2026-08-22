"""Emit one machine-readable module event for the native backend."""

import json

# Ansible exposes no typing marker, and loads this callback outside package context.
from ansible.executor.task_result import (  # type: ignore[import-untyped]
    CallbackTaskResult,
)
from ansible.plugins.callback import (  # type: ignore[import-untyped]
    CallbackBase,
)
from homelab_backend.ansible_result import (  # type: ignore[import-untyped]
    RESULT_PREFIX,
)


class CallbackModule(CallbackBase):  # type: ignore[misc]  # Untyped Ansible plugin API.
    """Keep human warnings separate from a single-line JSON result envelope."""

    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "stdout"
    CALLBACK_NAME = "homelab_json"

    def _emit(self, event: str, result: CallbackTaskResult) -> None:
        self._handle_warnings_and_exception(result)
        serialized = self._dump_results(result.result, indent=None)
        envelope = f'{{"event":{json.dumps(event)},"result":{serialized}}}'
        self._display.display(f"{RESULT_PREFIX}{envelope}")

    def v2_runner_on_ok(self, result: CallbackTaskResult) -> None:
        self._emit("ok", result)

    def v2_runner_on_failed(
        self, result: CallbackTaskResult, ignore_errors: bool = False
    ) -> None:
        del ignore_errors
        self._emit("failed", result)

    def v2_runner_on_unreachable(self, result: CallbackTaskResult) -> None:
        self._emit("unreachable", result)
