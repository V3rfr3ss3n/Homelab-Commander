---
title: Releases and compatibility
status: active
updated: 2026-11-11
tags: [wiki, maintenance]
---

# Releases and compatibility

A merged MR does not automatically authorize a release. Keep integration manifest,
Python project, App configuration and image/tag versions consistent. Preserve
`homelab_updates` identifiers and `/api/v1`; breaking contracts need a documented
migration and ADR.

## Release evidence

Before a release, require the source version-alignment gate, full local/CI gate,
independent HA/HACS validators,
secret/privacy checks, dependency review and the actual AMD64/AArch64 image/runtime
checks. Test installation and upgrade from the produced artifact in an isolated
HA environment. Never use a production homelab for development acceptance.

The release check and container policy reject mismatches among the project lock,
backend, integration, App, build and publish versions before publication. In an
isolated HA Supervisor test, confirm the newly published App is actually offered
as an update from the previous version, then verify installed/running versions
and persisted synthetic data after the normal App update. A Store reload timeout
or stale `version_latest` leaves this gate open; never count integration updates
as an App upgrade. A stable release requires this complete check.

The existing GitHub image pipeline builds PR/main changes without publishing.
Only the documented version-tag or explicit manual release path publishes public
versioned images using GitHub's short-lived workflow token. An anonymous manifest
and pull check confirms the App image is really available without credentials.

Do not change package visibility or enable publication as a side effect of a
regular MR. A failed dependency audit, unavailable image build or skipped install
check remains an open blocker, not a successful release.

Follow the [release runbook](../../04-operations/release-and-publication.md),
[public-install checklist](../../04-operations/public-install-checklist.md) and
[changelog](../../../CHANGELOG.md). Existing [migration notes](../../04-operations/migration-0.1-to-0.2.md)
cover the original provider transition.

## 0.3.0-dev.1 development prerelease

This candidate includes the backend dashboard, task compatibility/assignment and
readability follow-up. Back up the complete backend data directory before upgrade;
additive schema changes preserve IDs/history but downgrading requires restoration.
Migrated tasks need a successful compatibility check before their next execution.
Visible Dashboard/Hosts views request status checks every five minutes by default;
disable **Auto-check hosts** to opt out. Updates/reboots/custom tasks remain explicit.

After the versioned image and anonymous-pull gate pass, refresh the App store and
update **Homelab Commander Backend**. In HACS, enable prereleases/beta versions for
this custom integration, choose `0.3.0-dev.1`, update and restart Home Assistant.
The HA OS installation/upgrade walkthrough remains a manual acceptance step; CI
uses synthetic hosts and does not validate an operator's live installation.

## 0.3.0-dev.2 candidate

This candidate fixes controller-directory permission failures during host checks
in unprivileged containers. Ansible home and SSH control sockets now use private
per-invocation paths. No remote rights or persistence migration are added.
Unchecked host update/reboot state is displayed as unknown instead of false zeros.
The candidate must be merged and its versioned image must pass the publication
checks before the App can offer it as an update. After upgrade, explicitly request
**Check for updates** and inspect the resulting job; the failed earlier checks do
not establish that a host has no updates.


## 0.3.0-dev.3 development candidate

This candidate includes failed-job acknowledgement, guided account setup/update
scripts, working host removal and stable HTTP/HTTPS website icons with an optional
direct image URL. Sudo stays opt-in; icon loading bypasses no TLS or Cloudflare
policy. Review timestamps migrate automatically, and existing `/data`, host/task/job
identities and SSH keys remain intact. Updating the installed Backend App requires
no host recreation or integration reconfiguration. A standalone UI session expires
at restart and may require signing in again.

Publication requires the version-aligned commit and the full quality, HA/HACS,
security, native AMD64/AArch64 and anonymous image gates. The isolated artifact
upgrade uses synthetic data only. A full fresh HA OS/Supervisor install/upgrade
walkthrough remains a manual acceptance item, not an automated validation claim.
After publication, refresh the App store and update **Homelab Commander Backend**;
then reload its UI. The integration prerelease is also version-aligned, but these
backend UI fixes do not require deleting/re-adding the integration. Keep the normal
backup/recovery strategy; older binaries may not parse stored custom icon overrides.

## 0.3.0-dev.4 development prerelease

This development prerelease combines the timestamp timeline, job inspection/log tools, host
workspace, consistent action/system icons, compact filter reset and overlay
notifications. Active host guards and scoped counts cover all queued/running jobs,
including those outside recent history. **Update all** includes every eligible
host across the inventory, even when filters hide some targets; confirmation lists
the targets and requires maintenance/restart-review acknowledgement. Reboots remain
separate explicit actions.

The integration advertises update progress throughout queued/running jobs and
refreshes status at completion. Update the Backend App and integration separately,
then reload the integration and browser UI. Existing data/identities remain intact;
there is no new schema migration or production dependency for this candidate.

Source versions are aligned to dev.4. Publication requires green
quality, HA/HACS, security and native multi-architecture gates. The owner has deferred the isolated dev.3 image-upgrade and Supervisor Store
walkthrough for this development prerelease: the operator will check Store
discovery and the App upgrade after publication. These paths have not been
accepted in advance; a timeout or missing `version_latest` remains an open
acceptance defect. This is not stable-release installation acceptance.
Publication results are recorded in the
[release notes](https://github.com/V3rfr3ss3n/Homelab-Commander/releases/tag/v0.3.0-dev.4).
See the [candidate evidence](../../05-reviews/2026-11-11-dev4-stabilization.md) for
completed checks and remaining limits; individual MR runs are not release evidence.
