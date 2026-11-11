---
title: Updates and jobs
status: active
updated: 2026-11-11
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

The timestamp-based history graph is the main dashboard area. Choose the last hour,
24 hours, 7, 30 or 90 days, or enter a custom period up to 366 days. The graph
positions jobs by their stored event time; nearby jobs form a numbered group.
Hover or focus a point to see job previews directly around its original position.
The group count stays at the same point in the graph while individual job circles
open around it. On a touch screen, tap a group to expand its previews. A single point opens its job; the
center of a group opens the table filtered to that time window, including jobs
beyond the preview. The table button swaps graph and table in place. Job table
rows show local date/time, host, outcome, duration and safe error summary. The
exact timestamp remains in the tooltip. When a host is selected, the Dashboard, Hosts, Tasks and Jobs tabs retain that host
context. Dashboard and job history are scoped to it; Tasks shows its assignment and
compatibility controls; Jobs shows its recent work. The selection summary beside the header refresh button shows the selected host,
job detail or active filters. **Reset** clears them and returns the current tab to
its default view; it stays reachable while scrolling. The last job and last failed job also have
shortcuts below the graph. Counts use the full database rather than the limited
recent-job list.

Hosts, Tasks and Jobs have small find/filter/sort controls above their lists.
The dashboard shows up to five hosts and the full Hosts view shows all matches.
**Update all (N)** counts every eligible host across the full host list, even when
search or filters hide some hosts. The confirmation names the exact targets before
queuing their normal per-host update jobs. Hosts with unknown update status or an
active update are skipped and shown beside the count. If a target cannot
be queued, the message names it; verify its status before retrying. Restarts remain
separate actions. Each host row offers a **Check for updates** refresh icon,
**Update**, **Reboot** and **Details**.

Operation messages slide in as overlays near the top of the page without moving
navigation or content. Queued actions link to the exact job; batch updates link to
the update job list. Success messages dismiss after eight seconds and can also be
closed explicitly; errors remain until dismissed or replaced. Connection progress
and sign-in guidance appear when needed.

## Calmer overview and checks while viewing

The product title remains centered. Refresh and the selection/reset controls are
at the upper right. Between the primary tabs and **Auto-check hosts**, a compact
status dot indicates backend connectivity, followed by linked host, running-job and
queued-job counts. These links retain the selected host and open the matching views
from every tab. Latest-job highlights show
readable metadata previews and **Open job** / **Log preview** shortcuts. Log previews
are retrieved only after a click. Important notices sit beside the content on wide
screens, move into the flow on mobile and disappear when resolved. A successful
retry resolves the matching failure notice without erasing historical failures.
The history chart plots timestamped jobs; point tooltips retain exact UTC dates/counts.
Times are localized/relative, with original ISO values in tooltips and technical details.

**Auto-check hosts** is on by default and stored for this backend. While Dashboard
or Hosts is visible, it requests status checks at opening/resumption and every five
minutes. Recent hosts, hosts with active work and hosts within a shared five-minute
cooldown are skipped. Multiple open tabs do not duplicate work. Hidden/disconnected
pages and other views stop starting checks; accepted jobs may finish. Disable the
checkbox to opt out. The smaller refresh icon beside each host starts a manual check.
Status checks may refresh APT metadata; they never install updates or reboot.
Updates, reboots, host removal and custom task execution/deletion use accessible
in-app confirmations with a safe cancel action. Updates, reboots and custom tasks
still require explicit confirmation.

Until a host has a successful stored check, update and reboot status are shown as
unknown. Dashboard totals include only checked hosts and label any unchecked
hosts; unknown status is never presented as a successful zero-update check.
A failed first check leaves status unknown. Open its job for the failure reason.


## Inspect one job

Open a job from its history point, table row or action notification. The detail
workspace leads with the task/action name, host and outcome, followed by duration,
exit code, review state and a queued/started/finished timeline. Exact timestamps
and identifiers remain available in tooltips and **Technical details**. Host and
host-history links keep investigation close to the affected system; custom jobs
also link to the host's task configuration.

**Refresh job** fetches that exact job, including older jobs outside the recent
list. Active jobs update automatically. Logs appear when the backend has recorded
them. A log-fetch failure leaves the job summary available and can be retried with
**Refresh job**. Search output locally, move between matches, toggle line wrapping,
or explicitly **Copy log** / **Download .txt**. These tools use only the bounded,
redacted output already returned by the backend. A truncation notice means the
export is also incomplete. Inspect exported logs before sharing them. **Copy link**
copies the authenticated job URL without a token.

**Run again** creates a new job after confirming the action and exact host. It
preserves the original job and log, and the notification links to the new job.
Active jobs, missing hosts and hosts with mutating work block this shortcut.
Custom task reruns use the current task definition. They additionally require
current activation, assignment and suitable
prerequisites; otherwise open the host's tasks to resolve them. Backend checks
still apply when queuing and executing. An update rerun does not schedule a reboot.
Review acknowledges a failed job; rerunning it is a separate deliberate action.

## Review a failed-job notice

Follow **Review the job** from Important notices, inspect the log, then select
**Mark as reviewed**. This acknowledges that exact failed job for everyone using
this backend and persists across reloads/restarts. It removes that job from notice
selection without deleting history, changing failure status or retrying work.
Older unreviewed failures can then appear; new failures always need their own
review. Timeline points and group previews are red only while a failed job still needs
review. Reviewed failures and failures resolved by a later successful matching job
use a neutral point color; their recorded outcome and the historical failure curve
remain unchanged. A group is red if any matching job needs review, including jobs
beyond the six previews. The last-failed-job highlight remains historical. Security, reboot and
stale-host notices still reflect host state and are not dismissed by job review.
