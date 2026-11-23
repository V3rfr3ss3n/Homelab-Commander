---
title: Native package sources without a Commander catalog
status: proposed
updated: 2026-11-23
tags: [architecture, linux, packages, persistence]
---

# ADR-0032: Native sources without a Commander package catalog

Extends [ADR-0031](0031-automatic-system-manager-selection.md) after the owner's
explicit clarification. This is a review-branch decision, not a released feature.

## Ownership and transient observations

Native managers own repositories, installed state, versions, dependency resolution,
package locks and transactions. Commander adds no package inventory table or owned
package-to-manager mapping. Fixed adapter queries produce immutable bounded display
rows in memory. Before mutation, native eligibility is queried again; the display
cache is not authority. Updates delegate to native commands, without shell strings,
repository edits, signature bypasses, helper installation or automatic reboots.

Existing stored legacy cache bytes remain untouched by the additive migration.
Fresh checks stop writing package rows to SQLite. The nullable source-observation
column distinguishes legacy cached snapshots from fresh transient details: once a
new observation exists, only the matching in-memory snapshot supplies rows. After
restart, totals/time/source summaries remain but details require another native
check. This updates REQ-PKG-002 at the owner's request; it does not discard stored
host/configuration/job/SSH identity data. Explicit source choices and normalized
counts are host settings/status, not a package catalog.

## Native sources and operation references

`auto` discovers the supported system manager and optional Flatpak binary. Manual
`package_sources` selects system, default-system Flatpak and/or SSH-account Flatpak.
Legacy explicit manager configurations with no source setting remain system-only.
Pamac is not registered separately because its ALPM/Flatpak frontends share those
native stores. APT/Zypper on arbitrary unsupported hosts is not enabled merely by
finding executable files. Other users and named Flatpak installations are excluded.

A transient row's `name` carries `source::native-reference`; Flatpak refs encode
kind, ID, architecture and branch with colon separators. `source::` source markers
are instead `source::<source-id>` and represent a full source operation. Validated
references become immutable existing job parameters; no lookup table is persisted.
Legacy explicit-provider names stay compatible. Unqualified old auto selections
fail stale rather than being guessed across managers. New source choices affect
connection revisions; legacy null configuration retains the original revision.
Running jobs block source changes; queued jobs revalidate their configuration.

All source/selection scopes are checked before writing. Only selected sources need
mutation preflight; the following aggregate check refreshes all enabled sources.
All writes remain serial under the host conflict lock. Native locks are respected,
never removed. A later failure reports possible prior completion with no rollback,
retry or claim of cross-manager atomicity. An unavailable aggregate refresh marks
status stale rather than publishing zero or treating another source's success as
proof of whole-host completion.

## Native command limits and evidence

Flatpak adapters query app/runtime refs separately, join current installed origin
with native remote update listings, and invoke full refs with explicit system/user
scope. Upstream output uses partial installed refs and short commit IDs; parsers
validate those actual formats. These IDs are display provenance, not pinned update
commits. Native update policy resolves dependencies and may update/install required
runtimes or apply its normal end-of-life behavior. Security classification remains
unknown; Flatpak does not assert the host's reboot state.

Pacman admits synthetic Archlinux/CachyOS profiles with unknown security/reboot
signals. Preinstalled checkupdates performs safe inventory using its own native
temporary database; no isolated `pacman -Sy` or partial upgrade is offered. Full
maintenance uses `pacman -Syu --noconfirm`; repository signature checks, native
hooks, locks and configured exclusions remain. AUR/build helpers are excluded.
No application runtime dependency or permission increase is introduced. Operators
prepare native tools and SSH privileges independently; onboarding scripts remain
Debian/Ubuntu only. No real-host/platform certification is claimed.

## Migration and validation

Schema 16 adds nullable source configuration and summary JSON plus a running-job
source-change trigger. There is no data-deleting migration. Atomic rollback and
legacy UUID/count/revision preservation are tested. Back up `/data`; do not run an
older backend against new multi-source settings. Restore a suitable pre-upgrade
backup for downgrade. Native package stores are never migrated by Commander.

Required evidence includes native-only refresh, identical refs across installations,
single/selected/source/full scope, stale or forged selections, per-user non-root
execution, malformed output, partial failure without replay, migration rollback,
process-cache loss/repopulation, standalone/Ingress browser flows, and unchanged
independent 95% line/branch gates. Wiki publication and merge/release are separate.

## Primary references reviewed 2026-11-23

- [Flatpak command reference](https://docs.flatpak.org/en/latest/flatpak-command-reference.html).
- [Installed CLI formatting](https://github.com/flatpak/flatpak/blob/main/app/flatpak-builtins-list.c).
- [Remote CLI formatting](https://github.com/flatpak/flatpak/blob/main/app/flatpak-builtins-remote-ls.c).
- [Pacman native interface](https://man.archlinux.org/man/pacman.8.en).
- [Safe checkupdates inventory](https://man.archlinux.org/man/checkupdates.8.en).
- [Arch partial-upgrade policy](https://wiki.archlinux.org/title/System_maintenance#Partial_upgrades_are_unsupported).

Known per-source security counts remain visible as a known minimum even when
another source's classification is unknown. The aggregate security total remains
unknown; this must not hide a positive native security observation from UI alerts.
