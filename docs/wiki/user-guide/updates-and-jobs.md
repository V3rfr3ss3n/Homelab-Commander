---
title: Updates and jobs
status: active
updated: 2026-10-31
tags: [wiki, user-guide]
---

# Updates and jobs

## Read status

HA polls status centrally. Entity properties perform no network requests. Per-host
entities expose system updates, available/security update counts, distribution,
kernel, last check and reboot-required state. Native job/health metadata adds
backend connectivity, queue state, latest job and latest failed job.

The native operational sidebar panel is administrator-only. It displays hosts
and jobs; **Manage backend** opens the separate administrative interface. A
discovered local App opens through HA's App route in the current tab; an explicitly
remote backend opens its browser-reachable URL separately.

## Deliberate operations

1. Select **Check hosts** to create real native status-check jobs for managed hosts.
   Periodic HA polling reads stored status and is not an additional host-check button.
2. Review the target and start an update explicitly through its supported control.
3. Follow the job to its terminal state. A successful command triggers a fresh
   status read; that status determines the entity's final state.
4. If a reboot is required, confirm a **separate** reboot action. An update never
   schedules or performs that reboot implicitly.

The management UI requests confirmation for updates, reboots and custom tasks.
Avoid submitting another action while the target is already busy. Mutating native
jobs are serialized per host.

## Interpret jobs and logs

Jobs move through `queued` and `running` to `success`, `failed` or `cancelled`.
While jobs are active, the management UI automatically refreshes jobs and hosts
with a single poller. Terminal states stop fast polling; errors use bounded backoff.

The latest job and historical latest failed job are independent. A later success
does not erase historical failure information or make that old error the current
connectivity state.

Select **Open log** to retrieve bounded, redacted output explicitly. Logs require
authentication and are not stored in HA entity attributes or diagnostics. A
`#/jobs/<job-id>` link carries no token and still requires UI authentication.
Package names can reveal operational details: inspect a log locally and redact
it before sharing a minimal error report.
