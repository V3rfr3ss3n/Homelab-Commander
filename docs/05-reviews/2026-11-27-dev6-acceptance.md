---
title: Dev.6 Linux and upgrade acceptance
status: review
updated: 2026-11-27
tags: [review, linux, release]
---

# Dev.6 Linux and upgrade acceptance

Use the combined Linux MR branch. The preview is disposable and uses a
synthetic executor:

    uv run python -m homelab_backend.preview

1. Open Dashboard, Resources, Tasks and Jobs. Verify filters, job review,
   host grouping and task links.
2. Add a synthetic auto-detect host and check Package details. APT and the
   two Flatpak installations appear separately. Update one Flatpak and then
   one source. The other sources retain their counts. Re-enable a previously
   disabled source and check that completed updates stay completed.
3. Select Pacman for a synthetic host and run a package check. Expand
   Pacman upgrade preview and Foreign packages. Verify the extra solver
   candidate and the foreign package with unverified origin. Cancel a full
   upgrade and verify no job starts. Confirm one and recheck status.
4. Select Alpine 3.23 APK and repeat the full-upgrade flow. Verify single
   package controls are disabled and security/restart signals stay unknown.
   Smoke-test the existing APT, DNF and Zypper actions.
5. Before publishing, install the dev.6 artifact over dev.5 in an isolated
   HA Supervisor test with synthetic data. Verify host IDs, SSH fingerprint,
   UI settings, history and job review state. Reload the integration and
   check queued, running and completed update status. Verify store discovery
   and the App version when the release is published.

Automated checks exercise the dev.5 SQLite schema through schema 16, native
provider fixtures, and both Standalone and Ingress. The isolated HA Supervisor
artifact upgrade and Store discovery require separate evidence. The preview
does not certify native OS repositories or the Supervisor upgrade.
