"""Container bootstrap that translates add-on options and drops privileges."""

import json
import os
from pathlib import Path

_RUN_UID = 10001
_RUN_GID = 10001


def main() -> None:
    """Load optional Supervisor settings, prepare `/data`, then exec Uvicorn."""
    options_path = Path(os.environ.get("HUL_OPTIONS_PATH", "/data/options.json"))
    if options_path.is_file():
        raw = json.loads(options_path.read_text())
        if not isinstance(raw, dict):
            raise ValueError("Add-on options must be a JSON object")
        _set_option(raw, "api_token", "HUL_API_TOKEN")
        _set_option(raw, "log_level", "HUL_LOG_LEVEL")
        _set_option(raw, "allow_shell_tasks", "HUL_ALLOW_SHELL_TASKS")
        os.environ["HUL_INGRESS_MODE"] = "true"
    data_dir = Path(os.environ.get("HUL_DATA_DIR", "/data"))
    data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.geteuid() == 0:
        for root, directories, files in os.walk(data_dir):
            os.chown(root, _RUN_UID, _RUN_GID)
            for name in (*directories, *files):
                os.chown(Path(root) / name, _RUN_UID, _RUN_GID, follow_symlinks=False)
        os.setgroups([])
        os.setgid(_RUN_GID)
        os.setuid(_RUN_UID)
    os.execvp("homelab-updates-backend", ["homelab-updates-backend"])


def _set_option(options: dict[object, object], key: str, environment: str) -> None:
    value = options.get(key)
    if isinstance(value, bool):
        os.environ[environment] = str(value).lower()
    elif isinstance(value, str):
        os.environ[environment] = value


if __name__ == "__main__":
    main()
