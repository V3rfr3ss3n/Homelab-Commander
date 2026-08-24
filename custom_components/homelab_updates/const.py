"""Constants for Homelab Commander."""

from datetime import timedelta
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "homelab_updates"
NAME: Final = "Homelab Commander"
VERSION: Final = "0.3.0-dev.0"

PLATFORMS: Final = (
    Platform.UPDATE,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
)

CONF_SEMAPHORE_URL: Final = "semaphore_url"
CONF_BACKEND_TYPE: Final = "backend_type"
CONF_BACKEND_URL: Final = "backend_url"
BACKEND_NATIVE: Final = "native"
BACKEND_SEMAPHORE: Final = "semaphore"
CONF_STATUS_URL: Final = "status_url"
CONF_PROJECT_ID: Final = "project_id"
CONF_CHECK_TEMPLATE_ID: Final = "check_template_id"
CONF_UPDATE_TEMPLATE_ID: Final = "update_template_id"
CONF_REBOOT_TEMPLATE_ID: Final = "reboot_template_id"
CONF_EXPORT_TEMPLATE_ID: Final = "export_template_id"
CONF_POLL_INTERVAL: Final = "poll_interval"
CONF_VERIFY_SSL: Final = "verify_ssl"
CONF_NATIVE_CONNECTION: Final = "native_connection"

NATIVE_CONNECTION_LOCAL: Final = "local_app"
NATIVE_CONNECTION_REMOTE: Final = "remote"

NATIVE_APP_SLUG: Final = "homelab_updates"
NATIVE_APP_REPOSITORY: Final = "https://github.com/V3rfr3ss3n/Homelab-Commander"
NATIVE_APP_PORT: Final = 8099

DEFAULT_CHECK_TEMPLATE_ID: Final = 1
DEFAULT_UPDATE_TEMPLATE_ID: Final = 2
DEFAULT_REBOOT_TEMPLATE_ID: Final = 3
DEFAULT_EXPORT_TEMPLATE_ID: Final = 4
DEFAULT_POLL_INTERVAL: Final = 300
MIN_POLL_INTERVAL: Final = 30
MAX_POLL_INTERVAL: Final = 86_400
DEFAULT_REQUEST_TIMEOUT: Final = 15
DEFAULT_TASK_POLL_INTERVAL: Final = 3.0
DEFAULT_TASK_TIMEOUT: Final = timedelta(minutes=30)
MAX_STATUS_RESPONSE_BYTES: Final = 2 * 1024 * 1024

TASK_TERMINAL_SUCCESS: Final = frozenset({"success"})
TASK_TERMINAL_FAILURE: Final = frozenset({
    "error",
    "failed",
    "stopped",
    "cancelled",
    "canceled",
})
