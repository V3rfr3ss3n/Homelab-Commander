"""Fixed pre-schema-15 inventory shape for historical upgrade regressions.

Do not create old data through the current repository: it correctly requires the
current schema, and would silently stop testing the historical starting point.
"""

from backend.homelab_backend.database import Database
from backend.homelab_backend.models import Host
from backend.tests.test_automation import _host


async def legacy_host(database: Database) -> Host:
    host = _host()
    await database.async_execute(
        "INSERT INTO hosts(id,name,address,port,username,package_provider,"
        "created_at,updated_at,websites_json,packages_json) "
        "VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            str(host.id),
            host.name,
            host.address,
            host.port,
            host.username,
            host.package_provider,
            host.created_at.isoformat(),
            host.updated_at.isoformat(),
            "[]",
            "[]",
        ),
    )
    return host
