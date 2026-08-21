"""Safe integration-specific exceptions."""


class HomelabUpdatesError(Exception):
    """Base exception that never contains backend response data."""


class CannotConnectError(HomelabUpdatesError):
    """Raised when a configured service cannot be reached."""


class AuthenticationError(HomelabUpdatesError):
    """Raised when backend authentication fails."""


class InvalidProjectError(HomelabUpdatesError):
    """Raised when the configured backend project does not exist."""


class InvalidStatusDataError(HomelabUpdatesError):
    """Raised when the status response does not satisfy the contract."""


class InvalidUrlError(HomelabUpdatesError):
    """Raised when a URL is unsafe or malformed."""


class SemaphoreTaskError(HomelabUpdatesError):
    """Raised when a backend task cannot be started or completed."""


class TaskAlreadyRunningError(SemaphoreTaskError):
    """Raised when the same operation is already active."""
