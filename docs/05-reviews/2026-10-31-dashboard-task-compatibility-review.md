---
title: Dashboard and task compatibility review
status: reviewed
updated: 2026-10-31
tags: [review, backend, dashboard, security, testing]
---

# Dashboard and task compatibility review

## Delivered behavior

Dashboard is the management entry with complete queue/history aggregates, linked
notices and compact host/job lists. Full Hosts, Tasks and Jobs views use dialogs,
filters and stable deep links. Host creation includes public-key preparation for
Debian/Ubuntu and a validated versioned import envelope with explicit address choice.

Tasks declare prerequisites and use independent host assignments/activation. API
admission and workers enforce current suitability; workers probe again under the
host lock. Connection/task edits invalidate evidence, including edits during a
probe. Log redaction uses the actual immutable connection dispatched to execution.
An additive migration preserves host/task/job identities and legacy assignments;
operators must check migrated tasks before executing them again.

## Validation

- `UV_NO_SYNC=1 make quality`: passed, 330 tests; 98.36% lines and 95.71% branches,
  independently checked. Ruff format/lint, strict Mypy, documentation links,
  security exception checks, unfiltered dependency audit and privacy passed.
- `uv build --wheel --out-dir /tmp/homelab-dashboard-dist`: passed. The built wheel
  includes `frontend/index.html`, `frontend/ui.js` and `frontend/ui.css` with content
  identical to the reviewed source assets.
- Browser tests cover standalone and nested Ingress, mobile layout, host import,
  invalid versions/fields, compatibility/assignment/activation, job filters and F5
  deep-link recovery. Existing live-job polling regressions continue to pass.
- Setup and probe scripts run only with simulated system commands and synthetic
  isolated files/accounts. No managed host, SSH/Ansible execution, update or reboot
  was contacted or performed during validation.
- Published Wiki contents were compared with their marked source revisions before
  publication; unexpected remote edits were not found.

## Limits and handoff

No production dependency is added. Prerequisites cannot prove arbitrary task code
will succeed; shell dependencies must be declared. Package checks currently use
dpkg; onboarding offers Debian/Ubuntu only. Security notices lead to regular
updates, not a security-only package operation. SSH/sudo/network policy remains an
operator decision. Back up SQLite and the SSH identity before upgrade; older schema
downgrades are not supported. No merge, deployment or release approval is implied.

See [ADR-0012](../02-architecture/adr/0012-dashboard-task-compatibility.md) and
[quality gates](../03-development/quality-gates.md).
