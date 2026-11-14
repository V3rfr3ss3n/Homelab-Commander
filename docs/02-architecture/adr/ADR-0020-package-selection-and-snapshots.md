---
title: ADR-0020 Package selection and coherent status
status: accepted
date: 2026-11-14
tags: [architecture, backend, packages]
---

# ADR-0020: Package selection and coherent status

## Context

ADR-0019 used APT `state=present`, which need not upgrade an installed package.
Users also need to update several selected packages in one explicit job without
clearing unrelated update counts or accidentally upgrading the whole host.

## Decision

Preserve the no-body full update and legacy `package_name` request. Add mutually
exclusive `package_names` with 1–50 validated, unique APT package names. Empty,
ambiguous or malformed requests fail before enqueueing. Migration 10 adds a JSON
selection to jobs; existing single-package jobs retain their original field.
Persist a canonical sorted selection and recover it with the worker.

The adapter uses `state=latest only_upgrade=true` for a named package/list, without
`upgrade=dist`. APT may resolve dependencies; skip checkboxes are UI selection,
not package holds. Each update executes a fresh read-only check afterwards. Counts
and package rows are committed as one snapshot; failures retain the previous
snapshot. The package response includes the matching security count, and host
details render counts from this same response. No optimistic zeroing/decrement.

The dialog distinguishes Update selected from full Update all. Confirmation names
selected targets, explains dependency/full-upgrade effects and separate restart
review. Active work locks maintenance controls. Sorting and skip-all/select-all
never dispatch commands. Reruns preserve scope. An unrelated package success does
not acknowledge a failed selection. The 50-row display limit stays explicit;
full updates include packages outside that list, selections contain shown names.

## Consequences

This supersedes ADR-0019's APT state choice and extends its single-package contract.
There is no new production dependency, trust boundary or API version. Additive
migrations preserve existing IDs, data, preferences and SSH identity. Tests use
synthetic adapters/mocked modules and never update managed hosts.

## Links

- [Original scope decision](ADR-0019-scoped-package-update.md)
- [Native API](../native-api.md)
- [User guide](../../wiki/user-guide/host-package-details.md)


## 2026-11-15 verification clarification

The developer preview uses a versioned synthetic executor shared with regressions;
editor-local files only delegate to its entrypoint. Immutable adapter snapshots
reject counts smaller than their detail rows, inconsistent security counts and
negative values. Bounded partial detail lists remain supported. This prevents a
broken preview/adapter from silently storing contradictory package status.
