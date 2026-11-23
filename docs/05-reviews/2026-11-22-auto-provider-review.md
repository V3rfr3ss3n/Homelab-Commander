---
title: Automatic system package-manager selection follow-up
status: review
updated: 2026-11-22
tags: [review, linux, providers]
---

# Automatic system manager selection

Follow-up to #48 / GitLab !45 and GitHub PR #75, on the existing stacked branch.
The parent #47 review must land first; no merge, tag or release is performed here.

## Implemented

- New UI host configuration defaults to `auto`; API omission retains legacy APT
  for client compatibility. Existing stored explicit
  choices stay unchanged. No schema migration or runtime dependency is added.
- Validated distribution/manager facts select one supported system manager at
  the adapter boundary during an explicit check/update. No write-based discovery,
  fallback update, replay, implicit installation or reboot is introduced.
- Provider-specific admission remains in force. Unsupported or inconsistent
  facts fail before root/mutation; Tumbleweed inventory remains read-only.
- APT detection exposes observed scopes; new hosts cannot gain UI update controls
  solely because the configured policy is `auto`.
- Apply once, then collect fresh evidence. Architecture-qualified selections,
  nullable signals and failure recovery remain in place.

## Still open: multiple independent sources

The user also requested multiple selections per host. Clarification is pending
whether this means independent sources (for example system packages plus Flatpak)
or only system-manager discovery. The current inventory/job contract targets one
system manager. This follow-up does not claim multiple independent sources are
implemented. Such sources need separate identities, cache freshness, counts,
capabilities and immutable job references; selecting competing system managers
in a multi-select would not provide that behavior safely.

## Verification and local acceptance

The added synthetic provider cases cover APT, DNF, Zypper, exact single updates,
unsupported/mismatched discovery, detection failure, read-only admission and
preservation of explicit configuration. Chromium runs explicit and automatic RPM
configurations in Standalone and nested Ingress.

Run `uv run python -m homelab_backend.preview` after stopping an older preview.
New host configuration should show Auto-detect by default. Existing hosts should
retain their explicit selection. Check first, then update one simulated package;
the remaining list/count must agree. Explicit DNF and Zypper options remain.
The preview never connects to real hosts.

`UV_CACHE_DIR=/tmp/hlc-uv-cache make release-check`: 711 passed in 125.31 seconds;
98.63% line and 96.23% branch coverage, with both independent 95% gates retained.
Format, lint, strict types, docs, privacy, dependency audit and version alignment
passed. Additional focused Chromium execution: 4 passed in 5.96 seconds, including
the new-host default assertion. No managed host execution was performed.
Exact-commit remote results are recorded in the MR/PR. Wiki source
changes are prepared for review, not published under unrelated prior approvals.

## Owner clarification on 2026-11-23

The owner confirmed independent native sources and requested no Commander-owned
package catalog. The same MR now contains the follow-up in
[ADR-0032](../02-architecture/adr/0032-native-package-sources-without-catalog.md).
The earlier open clarification is resolved; scope and final evidence are recorded
in the 2026-11-23 review. No merge or release is implied.
