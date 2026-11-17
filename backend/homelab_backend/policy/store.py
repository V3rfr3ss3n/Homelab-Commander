"""SQLite adapters: immutable approval requests, atomic one-use and safe audit."""

import sqlite3
from datetime import datetime
from uuid import UUID, uuid4

from ..database import Database
from .application import AuditEvent, PolicyGuard
from .approvals import ApprovalRecord, ApprovalRequest, ApprovalState
from .domain import Permission, Principal


def append_event(connection: sqlite3.Connection, event: AuditEvent) -> None:
    connection.execute(
        "INSERT INTO authorization_events(id,at,principal_id,principal_kind,"
        "permission,target_id,code) VALUES(?,?,?,?,?,?,?)",
        (
            str(event.id),
            event.at.isoformat(),
            str(event.principal.id) if event.principal.id else None,
            event.principal.kind,
            event.permission,
            str(event.target.id) if event.target else None,
            event.code,
        ),
    )


class SqlitePolicyStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def async_append(self, event: AuditEvent) -> None:
        await self._database.async_transaction(
            lambda connection: append_event(connection, event)
        )

    async def async_create(self, request: ApprovalRequest) -> ApprovalRecord:
        def create(connection: sqlite3.Connection) -> ApprovalRecord:
            connection.execute(
                "INSERT INTO approval_requests(id,request_json,state) "
                "VALUES(?,?,'pending')",
                (str(request.id), request.model_dump_json()),
            )
            append_event(
                connection,
                AuditEvent(
                    uuid4(),
                    request.created_at,
                    request.requested_by,
                    Permission.APPROVAL_REQUEST,
                    request.target,
                    "approval_requested",
                ),
            )
            return ApprovalRecord(request=request)

        return await self._database.async_transaction(create)

    async def async_get(self, request_id: UUID) -> ApprovalRecord | None:
        row = await self._database.async_fetch_one(
            "SELECT * FROM approval_requests WHERE id=?", (str(request_id),)
        )
        return (
            ApprovalRecord(
                request=ApprovalRequest.model_validate_json(row["request_json"]),
                state=ApprovalState(row["state"]),
                decided_by=UUID(row["decided_by"]) if row["decided_by"] else None,
                consumed_by_job=UUID(row["consumed_by_job"])
                if row["consumed_by_job"]
                else None,
            )
            if row
            else None
        )

    async def async_decide(
        self, request_id: UUID, principal: Principal, approve: bool, now: datetime
    ) -> bool:
        def decide(connection: sqlite3.Connection) -> bool:
            row = connection.execute(
                "SELECT request_json,state FROM approval_requests WHERE id=?",
                (str(request_id),),
            ).fetchone()
            if row is None or row["state"] != ApprovalState.PENDING:
                return False
            request = ApprovalRequest.model_validate_json(row["request_json"])
            if request.expires_at <= now:
                connection.execute(
                    "UPDATE approval_requests SET state='expired' WHERE id=?",
                    (str(request_id),),
                )
                return False
            state = ApprovalState.APPROVED if approve else ApprovalState.REJECTED
            connection.execute(
                "UPDATE approval_requests SET state=?,decided_by=? WHERE id=?",
                (state, str(principal.id), str(request_id)),
            )
            append_event(
                connection,
                AuditEvent(
                    uuid4(),
                    now,
                    principal,
                    Permission.APPROVAL_DECIDE,
                    request.target,
                    str(state),
                ),
            )
            return True

        return await self._database.async_transaction(decide)

    async def async_consume(
        self, request: ApprovalRequest, job_id: UUID, now: datetime
    ) -> bool:
        def consume(connection: sqlite3.Connection) -> bool:
            if (
                request.expires_at <= now
                or connection.execute(
                    "SELECT 1 FROM approval_requests WHERE consumed_by_job=?",
                    (str(job_id),),
                ).fetchone()
            ):
                return False
            changed = connection.execute(
                "UPDATE approval_requests SET state='consumed',consumed_by_job=? "
                "WHERE id=? AND state='approved' AND request_json=?",
                (str(job_id), str(request.id), request.model_dump_json()),
            ).rowcount
            if changed:
                append_event(
                    connection,
                    AuditEvent(
                        uuid4(),
                        now,
                        request.requested_by,
                        Permission.EXECUTE,
                        request.target,
                        "approval_consumed",
                    ),
                )
            return bool(changed)

        return await self._database.async_transaction(consume)


def policy_for(database: Database) -> PolicyGuard:
    return PolicyGuard(SqlitePolicyStore(database))
