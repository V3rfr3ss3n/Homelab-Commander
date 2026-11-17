---
title: Resource jobs, conflict snapshots and uncertain-effect recovery
status: proposed
updated: 2026-11-17
tags: [architecture, jobs, recovery, migration, security]
---

# ADR-0026: Resource jobs and safe recovery

## Context

After the Registry and Groups foundation, #44 requires persistent resource targets,
immutable operation scope, caller context and deterministic conflicts. Previously,
startup requeued every running job, including updates, reboots and custom tasks.
An interrupted remote operation can have effects even when no result was saved.
This decision changes that recovery behavior; it does not promise exactly-once
remote execution. Owner approval/merge is pending for this implementation.

## Decision and boundaries

Keep one backend process and one bounded JobManager per database. The `execution`
package owns frozen typed scope/context values, canonical resource locks, SQLite
target resolution and job persistence. `jobs.py` remains the worker and preserves
old repository/type imports. Existing Host actions still use the Ansible executor;
HA, API and entities do not acquire SSH or SQLite responsibilities.

A scope records the exact ResourceRef, operation, optional execution Host, canonical
conflict references, package scope or task identity/revision and a connection
fingerprint. The fingerprint contains no connection values; tasks store a revision,
not command text. Changed connections, task revisions or Host associations reject
queued execution rather than silently executing new inputs. Legacy queued task
revisions are captured from the definition available during migration; unavailable
historical definitions cannot be reconstructed. Legacy jobs retain their original
Host UUID, but no historical connection fingerprint can be reconstructed.

Caller records the server-authenticated entrance: external administrator, standalone
UI administrator, Ingress administrator, visible status checks, internal application
or migrated legacy administrator. Current shared credentials do not identify an
individual person. No token, session ID, address or self-asserted request identity
is stored. Approval UUIDs are reserved for #46 and currently rejected, not grants.

## Conflicts and dispatch

Every Host operation (including status collection) holds that Host resource lock.
A Managed Service operation holds its resource and its associated Host, if present.
Hostless services lock themselves. Acquire deduplicated refs in `(kind, UUID)` order
and release all reservations on cancellation; unrelated resources remain concurrent.
Claim a queued job only after acquiring all conflicts. Recheck the snapshot before
dispatch and custom tasks after the existing fresh prerequisite check. Waiting for
a lock remains `queued`, not an interrupted running mutation.

Running service work blocks relinking/removing its inventory or Host relationship.
SQLite triggers reject changing a running job's Host connection or deleting that
Host; authenticated Host API routes return safe 409 responses. Rename/status updates
remain available. Queued work may be invalidated by metadata changes and then fails
closed. This is not a distributed lock manager, fairness guarantee or multi-process
worker architecture.

The generic service entrance is an internal, statically injected Protocol. Production
installs no handler, exposes no generic HTTP execution route and denies unknown
operations. A feature handler must authorize at enqueue and immediately before
dispatch; scope is revalidated after authorization. Approval references, groups,
tags and capability readiness grant no authority. Tests inject synthetic handlers
only. Generic parameters are deliberately absent until a feature supplies a typed
input contract. Generic output is withheld; only fixed safe completion/failure
messages and exit metadata are exposed. #46 is required before any real generic
mutation binding, and future features must extend target/conflict resolution safely.

## Additive schema 13 and compatibility

Add immutable `execution_json`, observed `interrupted_at`, preserved
`interrupted_started_at` and `recovery_count`. Backfill legacy Host targets, existing
package scope, task references and conservative recovery metadata in the same DDL/
version transaction. Jobs whose Host was already deleted retain a null execution
snapshot: do not invent a target. Migration does not change job states or enqueue
work. Preserve IDs, timestamps, logs/truncation, reviews, selections, settings,
resource/group data and SSH files. SQLite JSON functions are required (already
available on the supported runtime); no new dependency or SQLite version bump.

`/api/v1` retains existing endpoints, old fields and states. New execution/recovery
fields are additive. `resource_operation` is reserved for internal bindings and is
explicitly rejected by the UI Host-action route. No client-supplied caller, approval,
target override or implicit reboot. Backup DB and SSH state together; downgrade to
an older worker after schema 13 is unsafe because it can replay uncertain work.

## Startup and operator recovery

- Unstarted queued work survives and is revalidated before execution.
- Interrupted connection/status checks may resume; their prior start and observed
  restart are recorded. Existing APT metadata refresh is idempotent observational
  collection, not a package upgrade. No other action inherits this retry rule.
- Running update/reboot/custom/generic jobs become `failed` with
  `execution_interrupted`, preserving original start, logs and review state.
  Keep bounded existing output; only create a fixed safe explanation if absent.
- Uncertain failures remain review-required even after a later matching success;
  only explicit review acknowledges uncertainty. Review never retries an action.
- Operators inspect the resource and remote effects before explicitly creating new
  work. No automatic mutation retry, rollback, cancellation API or reconciliation
  provider is introduced. A forced stop while persisting a result is conservative:
  if completion is not recorded, the next startup reports uncertainty.

## Verification and follow-ups

Synthetic tests cover schema-12 upgrade/idempotence/rollback, unchanged legacy rows,
package/task preservation, Host/service conflict ordering, unrelated concurrency,
cancellation, default deny, dispatch reauthorization, changed snapshots, API auth/
CSRF/provenance, safe errors and real-browser standalone/nested Ingress recovery.
All remote operations are fake. Full quality, independent 95% line/branch thresholds
and applicable CI remain required. #46 supplies policy/approval authority; #45 and
later providers supply typed operation inputs/results and further conflict domains.
