---
title: ADR-0019 Scoped package updates
status: accepted
date: 2026-11-13
tags: [architecture, backend, ui, packages]
---

# ADR-0019: Scope package dialog updates

## Context

Package details expose individual pending packages, but their Update button used
the same host action as the full upgrade. This made the visible target misleading.

## Decision

The package dialog sends a validated `package_name` in the existing update action
request after an exact-package confirmation. Persist that optional value with the
job so worker recovery retains the requested scope. The APT adapter uses
`name=<package> state=present` for scoped jobs. An update without a package name
continues using the existing full `upgrade=dist` operation. Global Update all
actions send no package name and retain their full-host behavior.

## Consequences

An additive SQLite migration stores package names on jobs. Existing jobs migrate
with a null package name and preserve their behavior. `CHECK_UPDATES` and its
provider parser remain unchanged. No new dependency or API version is introduced.

## Links

- [Native API contract](../native-api.md#jobsemantik)
- [Package details guide](../../wiki/user-guide/host-package-details.md)
- [Package details decision](ADR-0018-package-details.md)

APT state choice and selection behavior are superseded by
[ADR-0020](ADR-0020-package-selection-and-snapshots.md); this record preserves
the original single-package decision.
