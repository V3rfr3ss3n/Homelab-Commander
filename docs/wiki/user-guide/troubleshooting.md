---
title: Troubleshooting
status: active
updated: 2026-10-31
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
