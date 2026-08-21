"""Compatibility imports for the integration's public client module."""

from .adapters.http import (
    SemaphoreClient,
    StatusClient,
    normalize_url,
    parse_hosts,
    parse_task,
)

__all__ = [
    "SemaphoreClient",
    "StatusClient",
    "normalize_url",
    "parse_hosts",
    "parse_task",
]
