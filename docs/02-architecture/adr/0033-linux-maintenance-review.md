---
title: Native Linux review, foreign provenance and Alpine maintenance
status: proposed
updated: 2026-11-27
tags: [architecture, linux, packages, review]
---

# ADR-0033: Native Linux maintenance review

Pacman review uses a temporary database initialized by checkupdates as the
SSH account. Pacman prints solver candidate names and versions and reports
foreign packages against the same sync view. Results are bounded and remain
in memory. Counts are separate from the upgrade inventory. A later status
observation or failed check invalidates the review.

Pacman's print mode does not promise a complete removal plan, a fixed
transaction or a restart verdict. Repositories can change before execution.
The host lock and policy govern execution of the explicitly authorized full
upgrade. Configured repositories may include third-party binaries.

## Foreign packages and AUR review

Absence from configured repositories does not prove AUR provenance. The
read-only inventory reports installed names and versions. It sends no host
inventory to an external metadata service and never downloads or executes
PKGBUILDs or invokes helpers.

A future administrator review must bind approval to the exact package base,
source revision, and reviewed bytes. Treat PKGBUILD and install scripts as
inert data. Inspect sources, dependencies and declared integrity data before
approval. A future execution design must use separate, bounded non-root
isolation with no host credentials or unrestricted network and a separate
decision to install the resulting artifact. No build or installation path
is exposed by inventory, approval or update-all in this MR.

## Alpine and Portage

Alpine 3.23 with apk-tools 3 offers native version inventory and whole-system
package upgrades through the existing SSH/Python/sudo policy. APK retains
repository and signature configuration. Security and reboot signals are
unknown. Single or selected updates and release changes are unavailable.

Gentoo Portage remains unavailable. A future adapter needs pinned profiles,
USE flags, slots, overlays and repository revisions, and reproducible native
pretend output for world selection, blockers, rebuilds and removals. Version
comparisons alone cannot establish safe transaction behavior.

## References

- [Pacman print mode](https://man.archlinux.org/man/pacman.8)
- [checkupdates temporary database](https://man.archlinux.org/man/checkupdates.8)
- [APK version table](https://github.com/alpinelinux/apk-tools/blob/v3.0.8/src/app_version.c)
- [Alpine 3.23 and apk-tools 3](https://www.alpinelinux.org/posts/Alpine-3.23.0-released.html)
