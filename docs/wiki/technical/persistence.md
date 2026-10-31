---
title: Persistence and job recovery
status: active
updated: 2026-10-31
tags: [wiki, technical]
---

# Persistence and job recovery

SQLite stores hosts, persistent jobs, bounded output and custom task definitions.
Host UUIDs remain stable independently of display names. The backend also persists
its ED25519 identity and isolated first-use `known_hosts` database under `/data`.
Private-key file permissions are `0600`; the API only exports the public key.

## Queue semantics

HTTP requests enqueue work and return jobs. A bounded worker executes queued jobs;
mutating operations are serialized per canonical host ID. Updates and reboots require
one existing explicit target. Missing/deleted targets fail safely before execution.

After a process restart, interrupted running jobs are requeued. This is recovery,
not an exactly-once guarantee. Operators should review in-flight operations before
restarting the backend. Do not introduce schema changes or new retry promises without
an explicit migration and acceptance plan.

## Stored output and HA metadata

Output is normalized, stripped of NULs, redacted for configured target/user values
and limited to 64 KiB. It remains sensitive operational data despite redaction.
HA receives compact job metadata only. Latest job and latest failed job are selected
independently so historical failures remain visible without replacing current state.

## Backup and migration

Back up the database and SSH identity together with a consistent procedure. Restoring
only the database loses the identity trusted by hosts. New persistence models need
an ADR, migration path and tests. Existing integration configuration cannot be silently
rewritten as part of a backend migration.

See [backup and recovery](../user-guide/backup-and-removal.md) and
[the backend boundary ADR](../../02-architecture/adr/0005-native-backend-boundary.md).
