# Changelog

## 0.3.0-dev.6 (development candidate)

- Adds native DNF, Zypper, Pacman and Alpine APK support alongside APT, with
  independently selectable system and Flatpak sources.
- Shows Pacman upgrade candidates and foreign packages with unverified origin.
  The preview requires checkupdates and runs with a temporary native sync database.
- Keeps package rows in memory and retains configuration, host IDs, jobs and
  SSH identity across the additive SQLite migration to schema 16. Back up data
  and review the upgrade checklist before installing.

## 0.3.0-dev.5

- Adds package details with name/security sorting, single updates, selected updates
  in one job, Skip all/Select all and a separate full Update all action.
- Keeps measured counts/rows while jobs run; updates installed packages with APT
  latest/only-upgrade and refreshes remaining packages after success. Failed jobs
  preserve the previous snapshot. Worker recovery and reruns retain package scope.
- Fixes readable check times in the dialog. Shows the 50-row detail limit and
  confirms full updates can include skipped/undisplayed packages and dependencies.
- Additive migrations preserve data and SSH identity. Existing hosts populate
  details after the next successful check. Package choices are UI selection, not
  persistent APT holds; review restart requirements separately.

## 0.3.0-dev.4 - 2026-11-11

- Timestamp job timeline with grouped previews, automatic filters and matching table.
- Richer job/host details, precise timings, log tools, consistent icons and a counted
  filter/reset control. Dashboard hosts appear below notices; notifications overlay
  the page. Host search and graph previews retain focus during navigation.
- Update all names every eligible inventory host, including hidden targets, and
  requires maintenance/restart-review acknowledgement. Reboots remain separate.
- Active counts and host guards cover all queued/running jobs beyond recent history.
- Preserve existing data and SSH identity; no new schema migration or production
  dependency. Reload the browser UI after updating the App. Update/reload the
  integration separately for the Home Assistant update-dialog progress fix.
- Development prerelease: automated quality/security/container gates are required.
  The owner deferred a separate Supervisor test instance; Store discovery and the
  actual installed upgrade will be checked by the operator after publication.

## 0.3.0-dev.3

- Adds persistent failed-job review and guided Debian/Ubuntu SSH user setup with
  configurable permissions and existing-user update scripts. Root sudo remains
  explicit and requires acknowledgement before copying. Scripts run only manually.
- Fixes host-removal navigation and exposes removal/user setup above Edit host fields.
- Keeps website icons stable across refreshes, tries common HTTPS SVG/PNG paths and
  supports direct icon URLs plus manual retry without weakening TLS/access checks.
- Preserves existing `/data`, hosts, tasks, jobs and SSH identity. The review-column
  migration runs automatically; no reconfiguration is required. Development prerelease.

## 0.3.0-dev.2

- Fixes local Ansible home and SSH control directory permission errors after the
  container drops root privileges. Host checks no longer fall back to root's home.
- Shows update/reboot status as unknown until the first successful host check;
  valid zero-update results remain zero. Dashboard totals identify unchecked hosts.
- No extra privileges, dependencies or data migrations are introduced by this fix.

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
