"""Explicit backend configuration from environment or tests."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    """Process configuration with no deployment-specific defaults."""

    data_dir: Path
    api_token: str
    log_level: str = "INFO"
    worker_count: int = 2
    allow_shell_tasks: bool = False
    ingress_mode: bool = False

    @classmethod
    def from_env(cls) -> Settings:
        """Load and validate settings from the process environment."""
        data_dir = Path(os.environ.get("HUL_DATA_DIR", "/data"))
        api_token = os.environ.get("HUL_API_TOKEN", "")
        if len(api_token) < 32:
            raise ValueError("HUL_API_TOKEN must contain at least 32 characters")
        log_level = os.environ.get("HUL_LOG_LEVEL", "INFO").upper()
        if log_level not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            raise ValueError("HUL_LOG_LEVEL is invalid")
        allow_shell_tasks = os.environ.get("HUL_ALLOW_SHELL_TASKS", "false").lower()
        if allow_shell_tasks not in {"true", "false"}:
            raise ValueError("HUL_ALLOW_SHELL_TASKS must be true or false")
        ingress_mode = os.environ.get("HUL_INGRESS_MODE", "false").lower()
        if ingress_mode not in {"true", "false"}:
            raise ValueError("HUL_INGRESS_MODE must be true or false")
        return cls(
            data_dir=data_dir,
            api_token=api_token,
            log_level=log_level,
            allow_shell_tasks=allow_shell_tasks == "true",
            ingress_mode=ingress_mode == "true",
        )

    @property
    def database_path(self) -> Path:
        """Return the persistent SQLite path."""
        return self.data_dir / "homelab_updates.db"

    @property
    def private_key_path(self) -> Path:
        """Return the persistent SSH private-key path."""
        return self.data_dir / "ssh" / "id_ed25519"

    @property
    def known_hosts_path(self) -> Path:
        """Return the isolated backend known-hosts path."""
        return self.data_dir / "ssh" / "known_hosts"
