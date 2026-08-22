"""Standalone UI session lifecycle tests."""

from collections.abc import Iterator

from backend.homelab_backend.ui_sessions import UiSessionStore


class FakeClock:
    """Controllable monotonic clock without real sleeps."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _tokens() -> Iterator[str]:
    yield "collision"
    yield "collision"
    yield "replacement"


def test_session_honors_idle_and_absolute_lifetimes() -> None:
    clock = FakeClock()
    store = UiSessionStore(
        clock=clock,
        token_factory=lambda: "session-one",
        absolute_lifetime=100,
        idle_timeout=20,
    )
    session_id = store.create()
    clock.now = 19
    assert store.authenticate(session_id)
    clock.now = 38
    assert store.authenticate(session_id)
    clock.now = 100
    assert not store.authenticate(session_id)

    second = store.create()
    clock.now = 121
    assert not store.authenticate(second)


def test_session_revoke_and_collision_handling() -> None:
    tokens = _tokens()
    store = UiSessionStore(token_factory=lambda: next(tokens))
    first = store.create()
    second = store.create()
    assert first == "collision"
    assert second == "replacement"
    assert store.authenticate(first)
    store.revoke(first)
    assert not store.authenticate(first)
    store.revoke(None)
    assert not store.authenticate(None)
