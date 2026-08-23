"""Short-lived in-memory authentication sessions for the standalone UI."""

import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass

UI_SESSION_COOKIE = "hul_ui_session"
UI_SESSION_COOKIE_PATH = "/ui-api"
UI_SESSION_ABSOLUTE_LIFETIME_SECONDS = 8 * 60 * 60
UI_SESSION_IDLE_TIMEOUT_SECONDS = 60 * 60


@dataclass(slots=True)
class _UiSession:
    """Server-only timestamps for one opaque browser session."""

    created_at: float
    last_seen_at: float


class UiSessionStore:
    """Issue, validate, rotate, and revoke process-local opaque sessions."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        token_factory: Callable[[], str] | None = None,
        absolute_lifetime: float = UI_SESSION_ABSOLUTE_LIFETIME_SECONDS,
        idle_timeout: float = UI_SESSION_IDLE_TIMEOUT_SECONDS,
    ) -> None:
        self._clock = clock
        self._token_factory = token_factory or (lambda: secrets.token_urlsafe(32))
        self._absolute_lifetime = absolute_lifetime
        self._idle_timeout = idle_timeout
        self._sessions: dict[str, _UiSession] = {}

    def create(self) -> str:
        """Create a collision-resistant session and opportunistically prune old ones."""
        now = self._clock()
        self._prune(now)
        session_id = self._token_factory()
        while session_id in self._sessions:
            session_id = self._token_factory()
        self._sessions[session_id] = _UiSession(created_at=now, last_seen_at=now)
        return session_id

    def authenticate(self, session_id: str | None) -> bool:
        """Validate both lifetimes and extend only the idle deadline."""
        if session_id is None:
            return False
        session = self._sessions.get(session_id)
        if session is None:
            return False
        now = self._clock()
        if self._expired(session, now):
            self._sessions.pop(session_id, None)
            return False
        session.last_seen_at = now
        return True

    def revoke(self, session_id: str | None) -> None:
        """Invalidate a presented session without revealing whether it existed."""
        if session_id is not None:
            self._sessions.pop(session_id, None)

    def _prune(self, now: float) -> None:
        expired = [
            session_id
            for session_id, session in self._sessions.items()
            if self._expired(session, now)
        ]
        for session_id in expired:
            self._sessions.pop(session_id, None)

    def _expired(self, session: _UiSession, now: float) -> bool:
        return (
            now - session.created_at >= self._absolute_lifetime
            or now - session.last_seen_at >= self._idle_timeout
        )
