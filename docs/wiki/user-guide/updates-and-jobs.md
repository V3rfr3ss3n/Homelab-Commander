---
title: Updates and jobs
status: active
updated: 2026-11-09
tags: [wiki, user-guide]
---

# Updates and jobs

## Read status

HA polls status centrally. Entity properties perform no network requests. Per-host
entities expose system updates, available/security update counts, distribution,
kernel, last check and reboot-required state. Native job/health metadata adds
backend connectivity, queue state, latest job and latest failed job.

Select **Homelab Commander** in HA's sidebar to open the backend management UI
directly in the current tab. There is no intermediate host/job overview. The sidebar
entry is administrator-only. A discovered local App opens through HA's App route
and Supervisor Ingress, keeping the HA navigation available. A remote backend opens
its configured browser-reachable URL and uses its own UI login; use Back to return
to HA. The integration does not forward its stored API token to the browser.

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

## Dashboard and job history

The management UI opens on Dashboard. It shows backend connectivity, host counts,
active queue counts, latest job and historical latest failure. Important notices
link to hosts with security updates, reboot requirements or missing/status checks
older than 24 hours, and to unresolved failed jobs. A security notice leads to
regular per-host updates; it does not offer a security-only update mode.

The compact host list and five recent jobs are shortcuts. **Hosts**, **Tasks** and
**Jobs** open full views. Each host row offers a **Check for updates** refresh icon, **Update**, **Reboot**
and **Details**; details contain connection testing, editing, deletion and tasks.
Jobs supports host/state filters and 25-item pages with a full matching count.
Dashboard's seven-day chart uses UTC calendar dates, with terminal jobs counted on
the completion date and active jobs on their creation date. Recent activity links
to completed jobs. Counts and historical failure query the full database rather
than the browser's capped recent-job list. Backend failures mark displayed data
as potentially out of date; refresh reconnects without starting host actions.

In normal operation, connectivity appears once in the dashboard's compact backend status badge.
Successful connection, refresh and navigation do not add status banners. Connection
progress and sign-in guidance appear when needed; errors and confirmations for
explicit operations remain visible.

## Calmer overview and checks while viewing

The header is centered; a compact green/red status dot indicates backend connectivity.
Hosts, running jobs and queued jobs share the top row. Latest-job highlights show
readable metadata previews and **Open job** / **Log preview** shortcuts. Log previews
are retrieved only after a click. Important notices sit beside the content on wide
screens, move into the flow on mobile and disappear when resolved. A successful
retry resolves the matching failure notice without erasing historical failures.
The history chart is a line graph; point tooltips retain exact UTC dates/counts.
Times are localized/relative, with original ISO values in tooltips and technical details.

**Auto-check hosts** is on by default and stored for this backend. While Dashboard
or Hosts is visible, it requests status checks at opening/resumption and every five
minutes. Recent hosts, hosts with active work and hosts within a shared five-minute
cooldown are skipped. Multiple open tabs do not duplicate work. Hidden/disconnected
pages and other views stop starting checks; accepted jobs may finish. Disable the
checkbox to opt out. The small refresh icon beside each host starts a manual check.
Status checks may refresh APT metadata; they never install updates or reboot.
Updates, reboots and custom tasks still require explicit confirmation.

Until a host has a successful stored check, update and reboot status are shown as
unknown. Dashboard totals include only checked hosts and label any unchecked
hosts; unknown status is never presented as a successful zero-update check.
A failed first check leaves status unknown. Open its job for the failure reason.


## Review a failed-job notice

Follow **Review the job** from Important notices, inspect the log, then select
**Mark as reviewed**. This acknowledges that exact failed job for everyone using
this backend and persists across reloads/restarts. It removes that job from notice
selection without deleting history, changing failure status or retrying work.
Older unreviewed failures can then appear; new failures always need their own
review. The last-failed-job highlight remains historical. Security, reboot and
stale-host notices still reflect host state and are not dismissed by job review.
