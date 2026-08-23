# Changelog

All notable changes to Homelab Updates will be documented in this file. The
format is based on Keep a Changelog and the project uses Semantic Versioning.

## [Unreleased]

### Added

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

- Integration and App packages now use the refreshed Homelab Commander icon in
  matching standard and HiDPI sizes.
- Home Assistant App Ingress now uses the Supervisor default root instead of
  producing a double-slash request, and installed App documentation links to the
  public repository.
- Native installation documentation now clearly separates the HACS integration
  from the Homelab Updates Backend App and documents internal App DNS.
- Restart buttons now use Home Assistant's restart device class and alert icon,
  are categorized as configuration actions, and are available only while the
  current status requires a reboot.

### Security

- Ingress management routes accept direct traffic only from the Supervisor
  proxy; `/api/v1` remains independently Bearer-authenticated.
- Backend credentials are confined to config entry data and request headers.
- Redirects and URL credentials, fragments, and queries are rejected.
- Diagnostics expose aggregate health information and fully redact the API token.
