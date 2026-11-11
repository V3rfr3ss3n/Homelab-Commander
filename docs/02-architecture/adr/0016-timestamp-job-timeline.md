---
title: ADR-0016 Timestamp job timeline and filtered management views
status: accepted
date: 2026-11-10
tags: [architecture, backend, ui, jobs]
---

# ADR-0016: Timestamp job timeline and filtered management views

## Context

Seven UTC day totals hide the actual order and spacing of jobs. A small recent-job
list cannot represent a busy backend. The dashboard needs a primary history view
whose grouped points lead to the exact matching job table.

## Decision

`GET /jobs/timeline` under both authenticated prefixes scans all stored jobs in a
bounded 366-day period. It groups by one of 12–120 equal-duration time buckets and
returns counts for every state plus at most six job previews per nonempty bucket.
Its timestamp is the average of the matching event times, not the calendar day's
center. Terminal jobs use `finished_at`, running jobs use `started_at`, and queued
jobs use `created_at`. The response includes inclusive bucket start and exclusive
end, allowing a group click to open the existing paginated job table at the same
period with preserved host, action and state filters. One-job points link straight
to their detail. Neither endpoint fetches job logs until selected.

The job page gains optional start/end, action and allowlisted sort fields without
changing the existing `/jobs` response. Start and end must be supplied together;
the range is at most 366 days. The UI provides presets, an explicit custom period,
a graph/table toggle and compact controls above Hosts, Tasks and Jobs. A combined
**Update shown** action targets only hosts displayed with known available updates,
asks for confirmation listing the targets, then queues individual existing update
requests and reports partial failures. It performs no implicit reboot.

## Consequences

The work adds no production dependency, migration or background action. Empty
periods show an explicit state. The timeline is bounded in response size even when
stored history grows; every count still covers the complete matching period.
Tests use synthetic jobs and both standalone and nested Ingress browser modes.

## References

- [Dashboard compatibility](0012-dashboard-task-compatibility.md)
- [Visible checks and websites](0013-visible-dashboard-checks-and-websites.md)
- [Native API](../native-api.md)
