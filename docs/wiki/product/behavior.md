---
title: Behavior and acceptance
status: active
updated: 2026-10-31
tags: [wiki, product]
---

# Behavior and acceptance

## Host and entity semantics

Technical host identity is stable and separate from display names. New hosts
appear without a reload; temporarily missing hosts become unavailable. Update
availability is determined by `updates > 0`; the security count is independent.
The last-check entity is a timezone-aware timestamp.

## Action semantics

Every update/reboot targets the exact technical host ID. Native actions create
persistent asynchronous jobs; HA tracks commands with bounded, cancellable polling.
Task completion removes tracking before notifying listeners of the final idle
state, so action controls do not remain falsely busy.

A successful backend command triggers a status refresh. Only refreshed status
determines the visible result. An update may report reboot required, but reboot
is a separate explicit operation. A reboot repair checks current state again
before acting on confirmed intent.

## Failure and access semantics

Status remains usable when only a separate command backend fails. Invalid external
payloads become safe errors; unknown additive data does not crash entities. Setup,
reload and unload leave no duplicate listeners or tasks.

The native HA panel and its WebSocket commands require administrator access.
Regular status streams contain compact metadata, not credentials or job output.
A separate authenticated action retrieves a bounded redacted log on demand.

## Acceptance evidence

Behavior changes need meaningful positive and negative-path tests. Coverage must
independently reach 95% lines and 95% branches, with no weakened security gates.
A release additionally needs HA/HACS validation, image checks and an isolated
installation from the actual release artifact. A green unit suite alone is not
a release approval.

The detailed [requirements](../../01-product/requirements.md) and
[acceptance checklist](../../01-product/acceptance.md) remain the normative records.
Dated reviews document a particular verification point, not permanent success.
