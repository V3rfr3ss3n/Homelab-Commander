---
title: ADR-0013 Visible dashboard checks and website shortcuts
status: accepted
date: 2026-11-09
tags: [architecture, backend, ui, security, persistence]
---

# ADR-0013: Visible dashboard checks and website shortcuts

## Context

The dashboard needs a calmer hierarchy, readable job previews, a line graph and
host website shortcuts. The owner explicitly requests automatic status checks by
default while looking at hosts, with an opt-out. Updates/reboots remain deliberate.

## Decision

Use a centered product heading, a compact status badge, three count cards and two
job highlights. Highlights preview safe metadata and link to the job; bounded log
previews load only on explicit selection. A responsive side panel highlights open
notices and disappears when empty. A later successful job for the same host, action
and custom-task identity resolves the corresponding failure notice, while historical
failure metadata remains available. A dependency-free SVG line graph shows seven
UTC days, with per-point values/dates. Human-readable actions and localized/relative
times keep original identifiers and ISO timestamps in tooltips/technical details.

Persist a backend-wide `enabled` UI preference, default true. A visible Dashboard
or Hosts view requests checks at opening/resumption and every five minutes; hidden,
disconnected and other views stop requesting checks. This is a UI client loop, not
a backend scheduler. An atomic database claim checks preference, freshness, existing
active jobs and a shared five-minute cooldown before queuing only `check_updates`.
Multiple tabs cannot multiply work. A request already accepted may finish after
hiding the page. Manual icon checks remain available. No update/reboot/custom task
is ever inferred or enqueued by this capability. A status check retains the existing
APT metadata refresh behavior; it installs no packages.

Additive migration 6 stores preferences, cooldown claims and per-host website JSON
without changing IDs or earlier records. Up to twelve named HTTP(S) links per host
reject userinfo. The browser opens links in a separate tab with `noopener noreferrer`
and fetches only each origin's `/favicon.ico` with no referrer; unavailable icons
fall back to initials. The backend never fetches websites/icons. CSP permits HTTP(S)
image sources only for this browser capability; scripts/connect policies remain
same-origin. Operators choose which sites their browser contacts.

## Consequences

No production dependency is introduced. HA polling still reads stored status and
is separate from visible UI checks. Website links remain backend inventory metadata,
not HA entity attributes. The five-minute interval is fixed in this iteration;
activation is shared/persistent and can be disabled in the UI. Existing sites start
empty. Backup/upgrade policies remain unchanged. Tests use synthetic adapters,
intercept all website requests, control browser time and verify visibility,
deduplication, disabling, URL validation and migration compatibility.

## References

- [Dashboard and task compatibility](0012-dashboard-task-compatibility.md)
- [Native API](../native-api.md)
- [Security and privacy](../../04-operations/security-and-privacy.md)
