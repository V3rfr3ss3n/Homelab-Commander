---
title: Manual groups, tags and bounded smart membership
status: proposed
updated: 2026-11-16
tags: [architecture, groups, security, persistence]
---

# ADR-0024: Bounded resource groups

## Decision and limits

Build #43 on the approved registry (#42, merged in !39). Keep grouping in its own
feature package: immutable rules/facts, application port, SQLite adapter, HTTP
schemas/router and separate browser workspace. No new dependency or execution
adapter. Schema 12 adds group UUIDs, manual membership and resource tags without
rewriting existing rows or touching SSH files. Rename/edit retains group identity;
deleting a group removes only its membership metadata. Multiple groups can contain
the same Host or service. Tombstoned resources disappear from effective membership;
their historical references remain stored. Names are not identifiers.

A group is either manual (up to 500 distinct resource UUIDs) or smart (no manual
overrides). Rules contain 1–16 positive exact predicates combined by `all` or `any`.
Fields are `type`, `distro` (case-insensitive exact), `tag`, `status`, `capability`
and `relationship`. A relationship requires an explicit counterpart UUID and edge
kind and matches an incident edge in either direction. No regex, expressions,
negation, nested rules, group references or arbitrary metadata evaluation. Empty,
malformed or unknown rules fail validation; invalid stored rules produce a safe
conflict and resolve no targets. No empty-rule match-all fallback.

Evaluation reads one coherent SQLite inventory snapshot. Budget: 5,000 active
resources and 20,000 relationships; exceeding either fails the request, never returns
a partial effective group. At most 32 tags per resource, lowercase ASCII slugs up to
48 characters. API pages have at most 100 rows, default 25, with explicit offsets;
search matches literal name substrings, and resource filters support type and tag.
Previews may display the first 100 matches with an explicit full count; API pagination
can inspect the remainder. All schema writes and membership replacements are atomic.

## Facts and trust boundaries

Host distro and status facts come from stored inventory only; no network probe.
Status predicates support the persisted `status` plus `updates_pending`,
`security_updates` and `restart_required`, only after a recorded check. They describe
the last observation, not a fresh health guarantee. Services/instances do not borrow
their associated Host's facts. Capability predicates use `name@major`, and match only
explicit supported evidence. No capability evidence producer is installed yet: the
current adapter returns no capabilities, hence these predicates match nothing.
The pure evaluator accepts immutable evidence for future typed adapters and tests;
provider bindings never imply capability support or connectivity.

The existing Bearer/session/Ingress boundaries protect metadata. UI mutations and
POST preview require CSRF. Preview never saves membership, mutates resources or
schedules jobs. Group/tag membership is not a grant, execution target or approval.
There is no group bulk-action endpoint. #44/#46 must independently expand, snapshot,
authorize and revalidate every effective target at execution. Later policy cannot
trust an old preview or silently widen agent permissions after a group edit.

## Threat model and maintenance

Reject executable/nested rule grammars and fail closed on bad stored rules. Bound
inventory, rules, pages and tag/member input to limit resource use. Parameterize SQL;
render metadata through text/escaping under existing CSP. Do not expose provider
configuration, host addresses, credentials or raw exceptions in group responses.
Pending browser requests are invalidated on logout; drafts are cleared and cannot
repopulate protected DOM. Request generations protect against stale inventory loads.
Concurrent administrator edits use atomic last-write-wins replacement; optimistic
conflict UI and group hierarchy are deferred. No privilege or permission changes.

## Validation and rollout

Use synthetic snapshots, databases and standalone/nested-Ingress browsers. Cover
multi-membership, hostless/linked services, all predicates and unknowns, invalid and
bounded rules, preview non-mutation, tag replacement, pagination/filtering, auth/CSRF,
persistence/restart, rollback and zero executor calls. Retain full quality/coverage
and container gates. Back up DB and SSH identity together before operator upgrades;
no downgrade guarantee after new group writes. No release accompanies this MR.
