# Changelog

All notable changes to Homelab Commander will be documented in this file. The
format is based on Keep a Changelog and the project uses Semantic Versioning.

## [Unreleased]

### Added

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
