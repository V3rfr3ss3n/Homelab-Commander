---
title: Releases and compatibility
status: active
updated: 2026-11-09
tags: [wiki, maintenance]
---

# Releases and compatibility

A merged MR does not automatically authorize a release. Keep integration manifest,
Python project, App configuration and image/tag versions consistent. Preserve
`homelab_updates` identifiers and `/api/v1`; breaking contracts need a documented
migration and ADR.

## Release evidence

Before a release, require the full local/CI gate, independent HA/HACS validators,
secret/privacy checks, dependency review and the actual AMD64/AArch64 image/runtime
checks. Test installation and upgrade from the produced artifact in an isolated
HA environment. Never use a production homelab for development acceptance.

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
