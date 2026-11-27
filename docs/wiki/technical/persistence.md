---
title: Persistence and job recovery
status: active
updated: 2026-11-23
tags: [wiki, technical]
---

# Persistence and job recovery

SQLite stores hosts, persistent jobs, bounded output and custom task definitions.
Host UUIDs remain stable independently of display names. The backend also persists
its ED25519 identity and isolated first-use `known_hosts` database under `/data`.
Private-key file permissions are `0600`; the API only exports the public key.

## Queue semantics

HTTP requests enqueue work and return jobs. A bounded worker executes queued jobs;
all Host operations and linked Service jobs share canonical resource locks. Updates
and reboots require
one existing explicit target. Missing/deleted targets fail safely before execution.

After a process restart, unstarted queued jobs resume after revalidation. Only
interrupted connection/status checks may be retried. Interrupted updates, reboots,
custom tasks and generic operations become failed with `execution_interrupted`.
Remote effects are uncertain: inspect the resource before explicitly starting new
work. Existing logs and the prior start are preserved. This is not an exactly-once
remote execution guarantee.

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

## Task assignment migration

An additive migration adds task requirement JSON, independent task/host assignments
and bounded compatibility metadata keyed by task and host. Existing tasks are
assigned to pre-existing hosts with their old enabled state; no check evidence is
invented. New hosts are not auto-assigned. Host/task deletion cascades assignment
and check records while existing job history retains its established deletion
behavior. Back up before upgrade; downgrade to an older schema is not supported.
Checks contain only safe reasons, timestamps and an input fingerprint, not command
output. They expire after 24 hours and connection/prerequisite changes invalidate
them. See [ADR-0012](../../02-architecture/adr/0012-dashboard-task-compatibility.md).

## Visible checks and website shortcuts

Migration 6 adds an empty website list to existing hosts, a backend-wide automatic
status-check preference (enabled by default), and per-host request timestamps.
Cooldown claims are transactional across tabs; host deletion removes the request
record. No background scheduler or automatic install/reboot is introduced.
Website links contain validated HTTP(S) URLs without credentials. Existing host IDs,
task assignments and job history remain intact. See
[ADR-0013](../../02-architecture/adr/0013-visible-dashboard-checks-and-websites.md).

## Failure review

Additive migration 7 adds nullable `jobs.reviewed_at`. Existing jobs remain
unreviewed; identities, logs and outcome metadata are preserved. A review records
the first acknowledgement timestamp idempotently and only accepts failed jobs.
Notice selection excludes reviewed failures, keeping the established later-success
resolution rule. The historical last failure remains independent. See
[ADR-0014](../../02-architecture/adr/0014-guided-setup-and-failure-review.md).

## Resource registry migration

Schema 11 backfills existing Host UUIDs without rewriting host/job/task records or
SSH identity. Atomic triggers keep legacy host creation, rename and removal in
sync. Host removal unlinks independent services; registry IDs remain as tombstones.
Active provider bindings are unique, and explicit VM/Host linking rejects ambiguous
identities. Migration, backfill and version marker share a rollback boundary; first
initialization is serialized off the event loop. Back up DB and SSH files together;
no safe downgrade after new writes is implied. See
[ADR-0023](../../02-architecture/adr/0023-resource-registry-and-module-boundaries.md).

## Groups and tags

Schema 12 adds group definitions, multiple manual memberships and resource tags. Host/service IDs and SSH state remain unchanged. Tombstones are excluded from effective membership; deletion removes only group metadata.

## Immutable resource job snapshots

Schema 13 adds credential-free target/operation/context snapshots and interruption
metadata without changing job IDs or states during migration. A queued job fails
closed if its target association, connection or task revision changes. Running work
blocks connection changes/removal and service relinking. Historical deleted Hosts
retain unavailable targets; no replacement identity is invented. Interrupted mutation
failures require explicit review even after a later success. Back up DB and SSH state
together; an older worker can replay uncertain effects, so a downgrade is unsafe.
See [ADR-0026](../../02-architecture/adr/0026-resource-jobs-and-safe-recovery.md).


## Authorization and approval migration

Schema 14 adds safe authorization events and immutable approval requests, without
rewriting existing job snapshots, IDs, settings or SSH state. New jobs retain a
credential-free principal; old snapshots derive the same legacy authenticated
entrance at dispatch. Decisions, denial, expiry and one-use behavior are enforced
by application policy; approval decisions/consumption are atomic with audit. An
approval's immutable expiry always applies even before any stored expired-state
sweep. This adds no background worker or approval execution route. See
[ADR-0027](../../02-architecture/adr/0027-central-policy-and-approval-contracts.md).


## Package evidence flags (schema 15, #48 review)

Add known-security and known-reboot flags plus observed package-scope JSON to
Hosts, without replacing IDs, previous values, SSH files or configuration.
Legacy rows default to their existing known values. The repository returns null
for unknown signals; SQL grouping respects known flags so internal storage
placeholders never become public zero/false claims. Migration DDL/version markers
are atomic and have a rollback regression.

Back up `/data` before deployment. Do not downgrade RPM-enabled data to code that
cannot interpret these flags; restore a pre-upgrade backup instead. Existing APT
values remain compatible. See
[ADR-0030](../../02-architecture/adr/0030-dnf-zypper-and-nullable-observations.md).

## Native-source cache boundary (schema 16 review)

Schema 16 additively stores optional source choices and source count/scope summaries;
no package catalog table is added. Existing package cache bytes are preserved by
migration. New native reads retain bounded package details in memory only. Once a
fresh source-observation marker exists, persisted legacy rows are not exposed as
current details. Counts/freshness survive restart; rows require a new native check.
Existing job parameters freeze exact source-qualified references, not ownership
maps. Null source settings preserve legacy connection revisions; explicit changes
invalidate queued work and are blocked during execution. Back up `/data` before
upgrade; downgrade requires a suitable pre-upgrade backup.

Dev.6 uses schema 16. Pacman solver candidates and foreign packages are
transient and tied to the same successful check as the package inventory.
They add no SQLite provenance records.
