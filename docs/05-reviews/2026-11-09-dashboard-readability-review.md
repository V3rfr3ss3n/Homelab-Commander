---
title: Dashboard readability and visible status checks review
status: reviewed
updated: 2026-11-09
tags: [review, backend, ui, security, testing]
---

# Dashboard readability and visible status checks review

## Behavior and boundaries

A centered heading, compact connectivity dot and aligned counts replace the bulky
status tiles. Latest job highlights offer metadata and explicit bounded log previews.
Unresolved notices occupy a responsive sidebar and disappear after recovery. Seven
UTC days are plotted as lines; readable dates retain exact ISO values in tooltips.
Multiple host rows preserve their own names, actions and Details links.

The owner explicitly requested default-on periodic status checks while looking at
the dashboard. Visible Dashboard/Hosts views request checks every five minutes;
hidden pages, other views and disconnect stop new requests. A persisted shared
preference disables them. Transactional claims avoid duplicates between tabs,
skip fresh/busy hosts and bound retries after failures. This only enqueues existing
status checks (including APT metadata refresh); it never installs or reboots.

An additive migration stores this preference, request cooldowns and up to twelve
validated website shortcuts per host. Website icons load in the browser without
referrers; links open independently with `noopener noreferrer`. Missing icons use
initials. Names are escaped in HTML attributes as well as text; credential URLs
and non-HTTP(S) schemes are rejected. The backend never fetches website contents.

## Evidence

`UV_NO_SYNC=1 make quality` passes: 341 tests, independently checked 98.41% line
and 95.83% branch coverage, Ruff format/lint, strict Mypy, documentation links,
security exception checks, dependency audit without ignores, and privacy scan.
`uv build --wheel --out-dir /tmp/homelab-refined-dist` passes; packaged assets and
service were compared byte for byte. Five affected Wiki pages matched their
marked source revisions before publication; no remote edits were overwritten.

Browser coverage exercises standalone and nested Ingress, desktop/mobile layouts,
line series/points, explicit safe log previews, website opening/editing and hostile
names, multiple hosts, controlled visibility/time, opt-out and resolved notices.
API/unit coverage verifies shared claims, cooldown/freshness, active jobs, deleted
hosts, preference persistence, CSRF/auth, website validation and retained history.
All execution uses synthetic adapters; website traffic is intercepted. No managed
host, SSH/Ansible command, installation or reboot is run by these checks.

The wheel contains byte-identical frontend assets and the visible-check service.
No production dependency is added. See [ADR-0013](../02-architecture/adr/0013-visible-dashboard-checks-and-websites.md).

## Limits

The preference is backend-wide; the five-minute interval is fixed. Already accepted
jobs may finish after a view is hidden or disabled. A favicon depends on the site's
standard `/favicon.ico`; sites without one show initials. Browser mixed-content
rules still apply to HTTP sites viewed from HTTPS. Back up before upgrading;
existing host IDs, task assignments and job history remain intact.
