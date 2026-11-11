# Changelog

All notable changes to Homelab Commander will be documented in this file. The
format is based on Keep a Changelog and the project uses Semantic Versioning.

## [Unreleased]

## [0.3.0-dev.4] - Unpublished

### Added

- Timestamp-positioned job timeline with grouped previews, automatic filters and
  a matching paginated table; red attention markers only for unresolved reviews.
- Compact job workspace with precise local timestamps, adaptive durations,
  searchable/redacted logs, copy/download controls and explicitly confirmed reruns.
- Host workspace with system/SSH facts, task assignments and recent jobs; consistent
  action/system icons, subtle update accents and prominent restart requirements.

### Changed

- Move host summaries below dashboard notices and status counts into the toolbar.
  Show notifications as overlays with job links and keep context/filter reset
  reachable through a counted funnel control.
- **Update all** targets every eligible host, including hosts hidden by filters.
  Confirmation names targets and requires maintenance/restart-review acknowledgement.
  Updates never request a reboot; reboot remains a separate confirmed action.

### Fixed

- Preserve active host counts and maintenance guards beyond the latest 100 jobs
  by loading queued/running pages independently of recent history.
- Advertise Home Assistant update progress so queued/running jobs remain visible
  in the update dialog until completion and the final status refresh.
- Test precise times and durations with explicit English and German browser locales.

### Upgrade notes

- Update the existing Backend App and integration, then reload the integration
  and browser UI. Existing `/data`, IDs, SSH identity and preferences are retained;
  no new persistence migration or production dependency is introduced.
- Source versions are aligned to dev.4. Publication requires all release gates,
  an isolated dev.3 artifact upgrade and Supervisor Store upgrade recognition.
  This candidate is not yet a published or accepted release.

## [0.3.0-dev.3] - 2026-11-10

### Upgrade notes

- Update the existing Backend App; no host/user/key recreation or integration
  reconfiguration is required. `/data` and existing host/task/job IDs remain intact.
- Migration 7 automatically adds failed-job review timestamps. Optional icon URLs
  use existing website JSON. Older backend binaries may not understand saved icon
  overrides; downgrade/restore is not an automatic rollback path.
- Development prerelease: use the normal backup/recovery procedure for protection
  against storage loss. Full fresh HA OS/Supervisor installation remains a manual
  acceptance step; automated checks use synthetic services and isolated artifacts.

### Fixed

- Keep website icons and failed attempts stable across refreshes; try modern icon
  paths and support an optional direct icon URL plus explicit retry in Edit host.

- Return to the host list after removal without reloading a deleted host's details.
- Expose removal and existing-user setup above Edit host connection fields, with
  in-dialog copy/error feedback and explicit inventory-only removal confirmation.

### Added

- Persistent **Mark as reviewed** for failed-job notices, keeping outcomes and logs.
- Guided Debian/Ubuntu host setup, configurable account/key/optional sudo scripts,
  existing-user update scripts and direct copying of visible previews.

### Changed

- SSH execution uses no TTY, matching restricted automation keys.
- Additive job-review migration preserves existing inventory and history.

## [0.3.0-dev.2] - 2026-11-09

### Fixed

- Use private writable Ansible home and SSH control paths per invocation when the
  backend container inherits a root home after dropping privileges.
- Show unknown update/reboot status before the first successful host check rather
  than misleading zero counts; dashboard totals identify unchecked hosts.

## [0.3.0-dev.1] - 2026-11-09

### Upgrade notes

- Development prerelease for testing; back up the complete backend data directory
  (SQLite and SSH identity) before upgrading. Additive migrations retain existing
  hosts, task IDs and job history; schema downgrade requires restoring the backup.
- Existing tasks retain their host assignments and activation, but require a
  successful compatibility check before their next execution. New hosts receive
  no assignments automatically.
- Visible Dashboard/Hosts views request status checks every five minutes by
  default. Disable **Auto-check hosts** to opt out. Checks may refresh APT metadata;
  updates, reboots and custom tasks still require explicit confirmation.

### Added

- Dashboard entry with compact connectivity/counts, linked job/log previews,
  resolved-notice sidebar and a seven-day line graph over complete stored history.
- Full Hosts/Tasks/Jobs views with setup dialogs, Debian/Ubuntu preparation commands
  and validated versioned paste import, filtered jobs and stable deep links.
- Declarative task prerequisites, expiring compatibility checks, per-host assignment
  and independent global/host activation enforced by API admission and workers.
- Per-host HTTP(S) website shortcuts with browser-only favicons, fallback initials,
  no-referrer requests and safe external links.


- English Wiki documentation with User Guide, Product, Technical and Maintenance
  sections, nested guides, a custom sidebar and versioned publication sources.

- Offline documentation file-link checks for Markdown and relative Obsidian
  links through `make docs`, included in the local and CI quality gate.
- Automatic local Homelab Commander Backend discovery on Home Assistant OS and
  Supervised, with health/token validation and an unchanged remote fallback.
- Public versioned AMD64/AArch64 app-image workflow with anonymous manifest,
  pull, health, tooling and non-root runtime verification.
- User-first HACS and Home Assistant App installation guide, release checklist,
  GHCR publication runbook and explicit branding replacement guide.
- Local 256 px and 512 px Home Assistant brand icons.
- Actionable reboot-required repair notification with an explicit confirmation
  flow.
- UI configuration, reauthentication, and reconfigure flows.
- Typed status and Semaphore HTTP adapters.
- Central status coordinator and asynchronous backend task tracking.
- Dynamic host devices with native update, sensor, binary sensor, and button
  entities.
- Global check and status refresh actions.
- Privacy-preserving diagnostics and English/German translations.
- HACS metadata, CI quality gates, security scanning, and public documentation.

### Changed

- Kept the contributor rename on the copyright line so GitHub/HACS can recognize
  the unchanged MIT license.

- Security-refreshed HA development lock, fixed development-only Pillow pin and
  unfiltered audits; resolved SE-2026-001 without renewing exceptions.
- HA schema-engine compatibility and explicit device-class imports for the new
  test baseline, retaining older Voluptuous installations.
- Agent rules now require task-specific Wiki reading, maintenance and reviewed
  publication of affected English source pages.

- Compact, task-based agent instructions shared by Codex and OpenCode, with
  preserved safety rules and current Homelab Commander component boundaries.
- Task-oriented Markdown documentation navigation and an explicit Wiki migration
  inventory that preserves the Obsidian vault and repository source of truth.
- GitLab/GitHub quality jobs pin uv `0.13.6` instead of older audited tooling.
- `make quality-fast` reuses existing checks for iteration; GitLab MR/main CI runs
  the complete quality gate without lowering coverage or publishing artifacts.

- User-visible product identity is now **Homelab Commander** while domain, App
  slug, module, API and persisted entity/config identities remain compatible.
- **Manage backend** opens a discovered local App through Home Assistant Ingress
  in the current tab; explicitly remote backends keep their external link.
- Integration and App packages now use the refreshed Homelab Commander icon in
  matching standard and HiDPI sizes.
- Home Assistant App Ingress now uses the Supervisor default root instead of
  producing a double-slash request, and installed App documentation links to the
  public repository.
- Native installation documentation now clearly separates the HACS integration
  from the Homelab Commander Backend App and documents automatic local discovery.
- Restart buttons now use Home Assistant's restart device class and alert icon,
  are categorized as configuration actions, and are available only while the
  current status requires a reboot.

### Security

- Ingress management routes accept direct traffic only from the Supervisor
  proxy; `/api/v1` remains independently Bearer-authenticated.
- Backend credentials are confined to config entry data and request headers.
- Redirects and URL credentials, fragments, and queries are rejected.
- Diagnostics expose aggregate health information and fully redact the API token.
