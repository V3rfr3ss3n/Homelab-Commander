---
title: Troubleshooting
status: active
updated: 2026-11-15
tags: [wiki, user-guide]
---

# Troubleshooting

## Setup or authentication fails

Check that the App is running and that the token matches. Remote URLs must be
reachable from HA; an Ingress browser route is not the external API endpoint.
If local discovery is unavailable, use the explicit remote/standalone flow.
Do not disable certificate validation globally or paste a token into a URL.

After a backend restart or expired standalone session, sign in again. A valid
session normally survives F5. Ingress and external API authentication are separate;
a browser cookie cannot authenticate an API client.

## Connection test fails

Verify the route from the backend to the host, SSH port, dedicated user, public
key, host fingerprint and Python 3. Then verify non-interactive sudo for the
intended operations. Do not add private keys to HA or enable host networking as
a general fix. The [host guide](hosts.md) explains the trust boundary.

## A status check or update fails

| Safe error code | First investigation |
| --- | --- |
| `python_interpreter_unavailable` | Python 3 exists and can be detected/executed |
| `sudo_unavailable` | Non-interactive privilege escalation is available |
| `apt_lock_unavailable` | Another legitimate package operation has finished; do not blindly delete locks |
| `check_updates_facts_failed` | Python/fact collection on the selected host |
| `check_updates_apt_cache_refresh_failed` | Privileged APT metadata refresh and repositories |
| `check_updates_package_list_failed` | Locale-stable package query |
| `check_updates_reboot_status_failed` | Reboot-marker status access |
| `invalid_ansible_output` | Structured callback/result contract, independently of warning text |

Zero updates, zero security updates, `changed=false` and no reboot marker are
normal successful results. A warning in job output is not itself a failure.
Inspect the authenticated, bounded log for the failed phase.

## Status appears stale

A successful task needs a status refresh before the displayed final state changes.
Check backend connectivity and whether the latest job is still active. An old
latest-failed-job sensor is history, not evidence that a newer successful job failed.
A temporarily missing host becomes unavailable rather than being removed.

## Report a problem safely

Include the product version, provider, deployment type, visible safe error code,
expected/actual behavior and synthetic reproduction steps. Do not attach HA
exports, private addresses, tokens, SSH keys, full job output or unredacted
screenshots. Report vulnerabilities through the private channel in
[SECURITY.md](../../../SECURITY.md), not a public issue.

Contributor pipeline failures are covered in [development and CI](../technical/development.md).

## Local Ansible directory permission errors

A job that reports permission denied creating `/root/.ansible` or its `cp`
subdirectory failed on the backend controller before collecting host status.
It does not establish that the host has no updates. The backend must direct its
Ansible home, temporary files and SSH control sockets to private writable paths;
adding privileges to the managed host cannot fix this local directory failure.
Before the first successful check, host rows display update/reboot status as
unknown and the dashboard identifies unchecked hosts. Previously collected
counts remain last-known values; inspect their check time and the latest job.


## Website icon missing over HTTPS

Opening a site successfully does not guarantee its `/favicon.ico` is an accessible
image. Commander tries five common icon paths and retains an initial when those
fail. For a different path, add a direct HTTP(S) image URL as the optional third
value in **Edit host → Websites**; see [website shortcuts](hosts.md#website-shortcuts).
Cloudflare challenges, authentication or browser privacy rules can block embedded
images independently of the site's main page. Use an accessible image endpoint;
never disable certificate verification. HTTPS targets are not retried over HTTP.

Regular refreshes retain both successful and failed icon states, preventing repeat
loads/flashing. Use **Retry saved website icons** after fixing the endpoint, or
reload the page. The retry uses saved website settings; save edited URLs first.

## Empty or unavailable job history

Graph and table share time/host/state/action filters. An actually empty result
shows an empty-state explanation. A failed request instead shows **History
unavailable**, or marks an already loaded result **stale** for the same filters.
Choose **Retry history** after checking connectivity. Changing filters does not
relabel stale data from a different query. A successful retry restores the view
and reports that history was refreshed.

Older system SQLite versions do not support the `subsec` date modifier and can
silently return no matches. Commander now converts persisted timestamps through a
registered function independent of that modifier. No database reset, reinstall or
host action is required; counts, timestamps and IDs are preserved.

## Copy useful failure diagnostics

Open **Technical details** on an error notification or history error, or
**Technical error details** on a job/log loading error, then **Copy diagnostics**.
The report contains version (or `unknown` before connection), component, static
operation, safe error code, UTC timestamp and HTTP status/reference where
available. A job request can include its technical job reference. It excludes
hostnames, addresses, tokens, request/response bodies and command output.
If clipboard access is unavailable, select the displayed details manually.

For example, report: version `0.3.0-dev.5`, operation `GET jobs / timeline`,
error `internal_error`, HTTP `500`, UTC time, the copied request reference and
synthetic reproduction steps. A backend administrator can find the same reference
and sanitized source location in backend logs. Worker failures use their job
reference in the protected job log. Logs are not automatically uploaded.

Persistent polling failures do not produce a new notification every cycle.
Recovery is indicated; automatic retry is limited to reads and the existing
visible status checks. Before repeating an update/reboot, inspect its job state.
Never attach full job logs, infrastructure screenshots or HA exports to a public
report. A red failed-job card records execution failure even after review; review
changes attention, not the recorded outcome.
