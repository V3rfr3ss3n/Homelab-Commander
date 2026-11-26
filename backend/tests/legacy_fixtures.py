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


def legacy_update_scope(host: Host):
    """Freeze the genuine pre-schema-16 execution identity without new columns."""
    import hashlib
    import json

    from backend.homelab_backend.contracts.resources import ResourceKind, ResourceRef
    from backend.homelab_backend.execution.scope import OperationScope

    target = ResourceRef(ResourceKind.HOST, host.id)
    revision = hashlib.sha256(
        json.dumps((
            host.address,
            host.port,
            host.username,
            host.package_provider,
        )).encode()
    ).hexdigest()
    return OperationScope(
        target=target,
        operation="linux.update",
        execution_host_id=host.id,
        conflicts=(target,),
        connection_revision=revision,
    )
