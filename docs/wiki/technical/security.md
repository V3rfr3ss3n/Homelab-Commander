---
title: Security and privacy
status: active
updated: 2026-10-31
tags: [wiki, technical]
---

# Security and privacy

All repository and Wiki content is public-safe, even when a page is technically
access restricted. Real infrastructure addresses, credentials, private keys,
configuration exports and unredacted logs never belong in project documentation.
Use synthetic examples such as `node-01` and `https://backend.example.invalid`.
A folder named technical or internal does not create an access boundary.

## Separate authorities

- HA stores the backend API token in its config entry and uses its shared session.
- The external API checks Bearer authentication; credentials are not logged.
- Standalone UI login creates an opaque in-memory HttpOnly session, with absolute
  eight-hour and idle 60-minute limits, strict cookie scope and HTTPS protection.
- Ingress trusts only the Supervisor proxy addresses resolved at startup for UI,
  assets and management routes. The external API still requires its token.
- UI mutations require CSRF. The HA panel and commands require administrator access.

## Limit disclosure and execution

Use allowlisted diagnostics and safe errors; never log authorization headers,
configuration dictionaries or full response bodies. Fetch bounded redacted logs
only on explicit authenticated selection. Render untrusted text as text and do
not persist tokens or logs in browser storage or HA state attributes.

The backend SSH key can be root-equivalent when used with non-interactive sudo.
Protect its file, backup and automation account. Updates and reboots remain explicit.
Tests use mocks, fixtures and synthetic execution adapters and never operate real
managed hosts, Semaphore tasks, updates or reboots.

## Security maintenance

Pins, audits, secret scans and privacy review are blocking gates. Expired exceptions
remain failures; do not extend an exception or suppress advisories merely to make CI
green. An upstream dependency pin can require a separately tested compatibility
migration. Read [the security policy](../../../SECURITY.md) for private vulnerability
reporting and [the full privacy model](../../04-operations/security-and-privacy.md)
before changing a trust boundary.
