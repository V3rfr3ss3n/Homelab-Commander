---
title: ADR-0018 Package details
status: accepted
date: 2026-11-12
tags: [architecture, backend, ui, packages]
---

# ADR-0018: Persist bounded package details

## Context

The host summary reports update counts but operators cannot see which packages
will change. Package manager output is available during the existing successful
check, while the host list must remain compact and updates remain explicit.

## Decision

Parse package rows during the existing provider pass and persist the first 50
normalized rows on the host record. Preserve the total parser count separately.
Expose rows through authenticated read-only per-host endpoints at
`/api/v1/hosts/{host_id}/packages` and `/ui-api/hosts/{host_id}/packages`. The
host detail view loads them on demand and offers a client-side security filter.
No package write action is added.

## Alternatives

- Compute on demand — rejected because it would need host I/O and could disagree
  with the last successful status check.
- Include an unbounded list in the host list — rejected because it expands every
  list response and stores unbounded provider output.
- Add a separate package table — rejected as overkill for a small bounded snapshot
  whose lifecycle is exactly the host status snapshot.

## Consequences

Migration 8 adds a JSON column with an empty-array default, preserving existing
host records. Checks store no more than 50 immutable typed package rows; the API
reports the full count. Existing hosts show package details after their next
successful check. No new dependency or provider protocol is introduced.

## Links

- [Native API contract](../native-api.md#paketdetails)
- [Product requirements](../../01-product/requirements.md#package-details)
- [Operator guide](../../wiki/user-guide/host-package-details.md)
