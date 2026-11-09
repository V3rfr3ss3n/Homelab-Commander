# Changelog

## 0.3.0-dev.1

- Opens directly on the backend dashboard, with compact counts/status, job and log
  previews, important notices, readable timestamps and a seven-day line graph.
- Adds full host/task/job management, SSH setup/import dialogs, task compatibility
  and per-host assignments, and named website shortcuts with favicons.
- Status checks run every five minutes while Dashboard/Hosts is visible by default;
  disable Auto-check hosts to opt out. Updates/reboots/tasks remain explicit.
- Back up the complete backend data directory before upgrade. Additive migrations
  preserve existing data; existing tasks require a compatibility check before use.
  Downgrade requires restoring a compatible backup. This is a development prerelease.

## 0.3.0-dev.0

- Renamed the visible product and App to Homelab Commander.
- Added integration-side discovery of the installed local App through Supervisor.
- Kept the existing `homelab_updates` App slug and persistent data compatible.

## 0.2.0-dev.1

- Updated the App Store icon and logo to the refreshed Homelab Commander brand.
- Fixed the default Ingress entry so the Supervisor forwards `/` instead of `//`.
- Restricted Ingress management routes to the Supervisor proxy while keeping the
  external API Bearer-authenticated.
- Replaced installed-App filesystem links with public GitHub documentation.

## 0.2.0-dev.0

- Initial public development build of the native Homelab Updates backend.
- Home Assistant Ingress management UI for hosts, jobs and custom tasks.
- Persistent ED25519 identity, SQLite state and bounded redacted job logs.
- Debian and Ubuntu update checks through the built-in Ansible execution adapter.
