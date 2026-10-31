"""Expiry remains blocking after the resolved exception is removed."""

from datetime import date

import pytest
from freezegun import freeze_time

from scripts import check_security_exceptions


@pytest.mark.parametrize(
    ("today", "expired"),
    [("2026-09-14", False), ("2026-09-15", False), ("2026-09-16", True)],
)
def test_exception_blocks_only_after_its_documented_expiry(
    monkeypatch: pytest.MonkeyPatch, today: str, *, expired: bool
) -> None:
    """A future exception cannot silently stay accepted beyond its deadline."""
    monkeypatch.setattr(
        check_security_exceptions,
        "SECURITY_EXCEPTIONS",
        {"SE-example": date(2026, 9, 15)},
    )
    with freeze_time(today):
        if expired:
            with pytest.raises(
                SystemExit, match="Expired security exceptions: SE-example"
            ):
                check_security_exceptions.main()
        else:
            assert check_security_exceptions.main() == 0


def test_no_active_security_exceptions() -> None:
    """The fixed stack needs no residual advisory exception."""
    assert check_security_exceptions.SECURITY_EXCEPTIONS == {}
    assert check_security_exceptions.main() == 0
