"""Fail the quality gate when a dependency security exception has expired."""

from datetime import UTC, date, datetime

# Resolved exceptions stay documented in the security register, not active here.
SECURITY_EXCEPTIONS: dict[str, date] = {}


def main() -> int:
    """Return failure when any documented exception is past its expiry."""
    today = datetime.now(UTC).date()
    expired = [
        exception_id
        for exception_id, expiry in SECURITY_EXCEPTIONS.items()
        if today > expiry
    ]
    if expired:
        raise SystemExit("Expired security exceptions: " + ", ".join(sorted(expired)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
