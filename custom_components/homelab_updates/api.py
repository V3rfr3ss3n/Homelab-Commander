"""Compatibility imports for the integration's public client module."""

from .adapters.http import (
    HttpStatusProvider,
    SemaphoreBackend,
    SemaphoreClient,
    StatusClient,
    normalize_url,
    parse_hosts,
    parse_task,
)
from .adapters.native import NativeBackendClient

__all__ = [
    "HttpStatusProvider",
    "NativeBackendClient",
    "SemaphoreBackend",
    "SemaphoreClient",
    "StatusClient",
    "normalize_url",
    "parse_hosts",
    "parse_task",
]
