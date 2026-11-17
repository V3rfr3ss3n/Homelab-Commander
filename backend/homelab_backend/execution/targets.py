"""SQLite boundary for atomic target snapshots and dispatch revalidation."""

import hashlib
import json
import sqlite3
from uuid import UUID

from ..contracts.resources import ResourceKind, ResourceRef


def resolve_target(
    connection: sqlite3.Connection, target: ResourceRef
) -> tuple[UUID | None, tuple[ResourceRef, ...]]:
    row = connection.execute(
        "SELECT kind FROM resources WHERE id=? AND deleted_at IS NULL",
        (str(target.id),),
    ).fetchone()
    if row is None or row["kind"] != target.kind:
        raise ValueError("Execution target is unavailable")
    host_id = target.id if target.kind is ResourceKind.HOST else None
    if target.kind is ResourceKind.MANAGED_SERVICE:
        service = connection.execute(
            "SELECT host_id FROM managed_services WHERE resource_id=?",
            (str(target.id),),
        ).fetchone()
        if service is None:
            raise ValueError("Execution target is unavailable")
        host_id = UUID(service["host_id"]) if service["host_id"] else None
    refs = {target}
    if host_id is not None:
        refs.add(ResourceRef(ResourceKind.HOST, host_id))
    return host_id, tuple(sorted(refs, key=lambda ref: (ref.kind, ref.id)))


def connection_revision(
    connection: sqlite3.Connection, host_id: UUID | None
) -> str | None:
    if host_id is None:
        return None
    row = connection.execute(
        "SELECT address,port,username,package_provider FROM hosts WHERE id=?",
        (str(host_id),),
    ).fetchone()
    if row is None:
        raise ValueError("Execution host is unavailable")
    return hashlib.sha256(json.dumps(tuple(row)).encode()).hexdigest()
