---
title: Releases and compatibility
status: active
updated: 2026-10-31
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
