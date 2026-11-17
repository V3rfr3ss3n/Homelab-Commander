---
title: Central policy choke points and immutable approval contracts
status: proposed
updated: 2026-11-17
tags: [architecture, security, policy, approvals, migration]
---

# ADR-0027: Central policy and approval contracts

## Context and decision

Issue #46 establishes M1 authorization and approval-domain contracts after the
Registry/Groups and [resource-job foundation](0026-resource-jobs-and-safe-recovery.md).
A feature readiness callback, group membership or request-carried approval UUID
cannot grant execution authority. Preserve existing explicit administrator Host
workflows, `/api/v1`, HA identities, SSH data, jobs and schema-13 recovery guarantees.
No new provider, agent account, automatic action, approval GUI or release is enabled.
This implementation is proposed for owner review.

The `policy` package separates pure principal/risk decisions, an application guard,
HTTP identity binding, immutable approval models/services and SQLite adapters. The
composition root injects the same guard into mutating services and the worker.
Legacy compatibility facades construct an equivalent default guard if not injected.
Domain values perform no I/O; adapters validate persisted JSON into frozen models.
No framework, ORM, runtime plugin loader or production dependency is introduced.

## Identity and trust boundary

`Principal` is an immutable internal UUID, kind and authenticated source, never a
token, session, endpoint or claimed display name. Kind/source combinations are
validated. Existing shared API credentials identify the external administrator
entrance, while authenticated UI/Ingress identifies the current trusted operator
entrance. These are stable channel identities, **not individual human attribution**.
Historical jobs derive their original channel without rewriting immutable JSON.
New jobs retain the actual server-bound principal across queueing and restart.

HTTP middleware begins every request anonymous. Existing Bearer, session and
Supervisor source checks bind an identity with guaranteed cleanup; a missing auth
dependency therefore cannot fall through to internal authority. Body fields and
headers never select a principal, role or approval grant. The optional injected
PrincipalResolver is a trusted server/test port, not runtime token provisioning.
Production still recognizes only its existing admin credential. Agent credentials
are not accepted by standalone login; non-admin identities cannot enter legacy
administration routes, even if a future/test resolver authenticates them.

Trusted internal Python composition retains the existing system identity for
legacy services and fixtures. This is not sandboxing arbitrary Python or writable
SQLite/SSH adapters. Untrusted automation must carry its own principal; it must
never be relabeled as system. Low-level persistence/execution adapters are not
public use cases. No agent receives internal Python execution or admin credentials.

## Default-deny and risk policy

The pure engine recognizes explicit permissions and registered operation policies;
unknown permission/operation/target kind, anonymous, agent and automation execution
deny. Visible-status authority permits only the existing observational checks and
status persistence; it cannot update packages, reboot, run tasks or edit metadata.
Admin service boundaries guard Host/task metadata, probes/assignments, registry
writes, groups/tags, preferences, job review, key export and setup generation.
Existing authentication and CSRF remain additional mandatory boundaries.

All job entrances apply policy before persistence, and the worker checks serialized
authority again under the canonical resource locks before dispatch. Custom tasks
retain their enablement/assignment/fresh-probe checks. A feature callback may deny
readiness but cannot override central denial. Generic operations require an explicit
static policy declaration as well as a handler; production installs no handler.
Only the five existing Host operations have compatibility rules for existing
explicit admin actions. Registration cannot extend that exception to new operations.
Legacy updates/reboots/custom tasks retain current confirmation contracts, not a
new mandatory approval workflow; package update and reboot remain separate actions.

New disruptive/destructive operations require the approval service. Other new
operations require an explicit registered policy and compatible administrator
identity. M1 installs no agent/automation execution grants, configurable policy
editor, permission delegation or autonomous update policy. M6 must add restricted
credentials, current role/revocation lookup and reviewed exact-target rules before
any such activation. Technical capabilities and group/tag selection are not grants.

## Immutable approval lifecycle

Requests record UUID, requester identity, exact resource and operation, risk class,
a SHA-256 digest of the immutable typed scope/parameters, observed-state digest,
creation and expiry (at most fifteen minutes). Request content is frozen and cannot
be updated in SQLite. Pending approval is **not a queued job**.

Only a human UI/Ingress principal can decide pending requests. API administrators,
system code, agents and automation cannot exercise that service, and agents cannot
approve their own proposals. API/GUI approval endpoints are deliberately absent;
M6 must establish nondelegable individual human identity and show complete typed
scope, risk, state and expiry before providing that operator surface.

States are pending, approved, rejected, expired and consumed. An observed expired
pending decision becomes expired; an approved request is effectively unavailable
once its expiry is reached, even if its stored state has not been swept. Rejected,
expired and consumed decisions cannot be approved again. No expiry scheduler or
background mutation is added.

Execution validates approved state, expiry, exact requester/source, resource,
operation, scope digest and current risk policy. A required StateValidator must
recheck authoritative observed/prerequisite state; no permissive production default
exists. Job target/connection/task snapshots are revalidated as in #44. Under the
resource locks, consume atomically for one generated job UUID immediately before
dispatch. Concurrent consumers cannot both succeed. A crash after consumption never
replays uncertain effects or restores the approval. An approval does not upgrade an
agent to an execution principal: agent execution remains denied in M1 even after a
human accepts its proposal.

Future providers must supply typed parameters/results, scope display and authoritative
state/version checks. This local contract cannot make remote state changes atomic,
guarantee exactly-once effects or detect every out-of-band change. No arbitrary JSON,
command body, credentials or untrusted provider text enters an approval or audit.

## Additive schema 14, audit and compatibility

Add `approval_requests` and `authorization_events`; do not modify old records or
job execution JSON. DDL and version marker share the existing rollback transaction.
Job context adds an optional principal; old snapshots without it remain readable and
queued jobs retain the legacy authenticated entrance. SSH identities, configuration,
resource/job/task/Host IDs, logs, reviews and package selections remain unchanged.
Existing schema-13 downgrade restrictions still apply.

Authenticated policy denials persist safe event ID, UTC time, principal UUID/kind,
permission, optional target UUID and static reason code. Approval request/decision/
consumption transitions are audited in the same transaction as their change.
Tokens, headers, names, infrastructure addresses, task commands, parameters,
exception messages and provider output are excluded. No sensitive audit dump API or
telemetry is introduced. Credential rejection remains the existing authentication
boundary; it is not mislabeled as an authenticated policy decision. Denial audit
failure prevents the action from proceeding. Repeated valid polls create no audit
spam; retention/rate control for untrusted future callers remains required before
publishing those entrances.

HTTP policy failures keep compatible `detail` plus existing sanitized diagnostics
and status 403. The UI distinguishes policy rejection from expired Ingress
authentication and preserves valid sessions. Worker denial becomes a safe failed job and existing Important
notices/review behavior applies. No automatic retry of denied writes. Full synthetic
bypass, lifecycle, expiry, race, migration and existing standalone/Ingress/HA gates
remain required, with independent 95% line and branch coverage.
