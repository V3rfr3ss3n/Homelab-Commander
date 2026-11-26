---
title: Native multi-source follow-up review
status: review
updated: 2026-11-23
tags: [review, linux, packages, privacy]
---

# Native sources in the existing #48 review

The owner confirmed independent native package sources and asked to extend the
existing MR without creating a Commander-owned package catalog. Changes remain on
`feat/dnf-zypper-providers`, stacked on #47. No merge, tag, version bump or release.

## Delivered

- Automatic or manually chosen system/default-system Flatpak/SSH-user Flatpak
  sources. Pamac is not counted as another native store.
- Native query output is validated at adapters; no installation catalog, repository
  mirror, package ownership table or new production dependency is added.
- New rows remain in a bounded transient UI cache. Native managers are queried for
  current eligibility before updates. Existing legacy cache bytes are retained
  additively, never used as routing authority; source/count/time summaries persist.
- Single, selected, full-source and full-host updates preserve exact source/native
  references in existing immutable job parameters. Same Flatpak IDs across user/
  system installations, kinds, architectures and branches remain distinct.
- Fixed source-scoped native argv, serial host locking, no signature/lock bypass,
  no cross-manager atomicity claim, rollback, automatic write replay or reboot.
- Archlinux/CachyOS Pacman supports full upgrades only. Native checkupdates uses
  its own temporary native sync database. Preinstalled tools are required; AUR,
  package installation/removal workflows, named Flatpak installations, other
  desktop users and unsupported APT/Zypper combinations remain outside this block.
- Known native security counts remain alertable even if another source has no
  classification; the aggregate total stays unknown.
- Source failure before a write stops the operation. A later failure reports
  possible earlier completion; aggregate read failure retains stale counts. Source
  edits invalidate queued revisions and are blocked while jobs run.
- Preview source selection changes retain prior simulated update progress. All
  fixtures are synthetic and no real host or package-manager action was executed.

## Compatibility and migration

Schema 16 adds nullable source configuration/summary columns and a source-change
trigger. It performs no global deletion or rewrite of existing cache data. Null
configuration preserves old connection fingerprints; legacy response fields stay
compatible and absent optional row/source fields are not added as null/empty noise.
The immutable historical job fixture was updated to construct the original scope
without querying columns absent in that genuine old schema. Existing before/after
identity, state and authority assertions remain.

Older preview/browser tests now query the manager after cache loss rather than
assuming a newly created application owns another repository instance's transient
rows. Stored totals survive; exact row assertions remain after native refresh.

Back up `/data` before adoption. Downgrade to a backend that does not understand
source configuration requires a suitable pre-upgrade backup. Synthetic tests and
Commander container runtime checks do not certify real Arch/Flatpak installations.

## Validation

- `UV_CACHE_DIR=/tmp/hlc-uv-cache make release-check`: **762 passed** in 142.76
  seconds, **98.41% line / 95.33% branch coverage**, independently above 95%.
- Format/lint, strict Mypy (104 production files), documentation links (0 errors),
  privacy, dependency audit (no known vulnerabilities), and version alignment
  `0.3.0-dev.5` passed. No version/release change is included.
- Focused native-security and standalone/mobile Ingress source suite: 39 passed;
  focused source preview/browser/persistence/legacy-preview suite: 28 passed.
- Genuine old-schema fixtures remain pinned; no identity/state/authority assertions
  were removed. Legacy response shapes and exact original confirmation wording
  remain covered; fresh native reads are required after transient cache loss.
- Final exact-commit GitLab/GitHub checks and AMD64/AArch64 container build/runtime
  contracts are recorded in the MR. These are synthetic/packaging evidence, not
  real managed-host or OS installation certification.

Independent 95% line/branch thresholds are unchanged. All native execution was
injected/synthetic; no real host update, bootstrap, reboot or package installation
was performed.

## Local acceptance

Stop an older preview and run:

```sh
uv run python -m homelab_backend.preview
```

Open the loopback UI. Create a synthetic host with Auto-detect and run a check in
Package details. Expect separately labeled system, system Flatpak and SSH-user
Flatpak rows. Update one Flatpak and verify only that row/installation disappears
and counters agree. Try Skip all/selection, Update source and Update all. Switch
source choices away and back: completed simulated updates must not reappear.
Choose Pacman with explicit sources for a simulated CachyOS workspace; individual
system updates are disabled, full source updates work. Confirmations remain
required and no reboot is automatic. Check narrow/mobile layout and preserved
ordinary APT/jobs navigation. Never enter real infrastructure into test fixtures.

## Wiki and follow-up

Affected Wiki sources are prepared for review, not published under unrelated prior
page approvals. Remote edits and owner authorization must be checked for the newly
reviewed snapshot. Review and merge follow the owner's local acceptance; a Dev
release is a separate explicit request. The parent #47 review must land first.
