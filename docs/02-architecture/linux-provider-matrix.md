---
title: Linux provider capability and compatibility matrix
status: proposed
updated: 2026-11-23
tags: [linux, providers, capabilities, testing, compatibility]
---

# Linux provider matrix (#47)

This is the contract and synthetic-adapter baseline for M2, not real-platform
certification. **APT, DNF, Zypper, Pacman and Flatpak adapters are registered in the #48 review branch.**
DNF supports the declared Fedora/RHEL-family baseline; Zypper mutations target
Leap 16.0. Tumbleweed inventory is read-only with empty observed update scopes.
Native cases use manufactured outputs; no real OS certification is claimed. The apk/Portage rows specify future compatibility targets and missing evidence. The `auto` configuration detects the supported system manager from validated
Ansible facts when an explicit check or update runs. It never tries updates to
discover a manager. No automatic updates, reboot or plugin installation is
introduced. Configured RPM providers validate detected target facts before dispatch.

## Version targets and evidence levels

The APT baseline uses manufactured Debian 12 and Ubuntu 24.04 facts/outputs; it does
not certify real OS installations. Existing APT configuration is not version-gated
and remains unchanged. Other Debian/Ubuntu versions are unverified here, rather
than newly blocked or silently certified. Derivatives require their own evidence.
No per-version real-installation certification is claimed by this test suite.

The targets below are deliberate candidate baselines, **not latest-release or vendor
support-lifetime assertions**. Future activation must record exact patch release,
manager version, architecture, image digest/repository snapshot and test evidence.
Rolling distributions require a pinned repository snapshot; Gentoo also requires
profile, USE flags and repository commit. Container runtime tests of Commander do
not certify the target operating systems. AMD64 and AArch64 host coverage must be
recorded separately before advertising either.

## Operation and signal matrix

`scopes` describes current Commander capability readiness: supported = implemented
operation for the admitted profile; unavailable = intended operation without an installed adapter;
unknown = safety/implementation evidence unresolved; unsupported = deliberately
excluded for this workflow. No non-supported state authorizes an action. An
implemented operation still needs host readiness, permissions and job checks.

Signal states have a separate meaning: known = an actually reported value under a
specified collector's semantics; unknown = no reliable conclusion; unavailable =
a defined source cannot currently be collected; unsupported = no defined collector
in this contract. None of the last three means numeric zero or boolean false.
The future-family signal cells are **synthetic missing-evidence scenarios**, not
claims about whether their package managers provide security/reboot facilities.

| Profile | Candidate versions / required pins | Full | Single | Selected | Security case | Reboot case |
| --- | --- | --- | --- | --- | --- | --- |
| apt | Debian 12; Ubuntu 24.04 | supported | supported | supported | known | known |
| dnf4 | RHEL 9; Rocky Linux 9; AlmaLinux 9 | supported | supported | supported | unknown | unknown |
| dnf5 | Fedora 45 | supported | supported | supported | unknown | unknown |
| zypper | openSUSE Leap 16.0 | supported | supported | supported | unknown | known |
| pacman | Arch Linux (snapshot required) | supported | unsupported | unsupported | unknown | unknown |
| apk | Alpine 3.23 | unavailable | unknown | unknown | unknown | unknown |
| portage | Gentoo (profile and repository commit required) | unknown | unknown | unknown | unknown | unsupported |

The machine-readable companion is
[`provider-matrix.json`](../../backend/tests/fixtures/linux/provider-matrix.json).
Tests prevent its rows and this table from diverging. It is a test manifest, never
a runtime provider catalog or permission source. AUR is separate from official
pacman and unsupported for building/installing in this block (#50 needs its own
review); automatic execution of PKGBUILDs, root builds and helper installation are
not authorized.

## Semantics which adapters must preserve

- **APT:** preserve current cache refresh, `dist` full update and installed-package
  single/selected `latest` behavior. Status counts matching upgradable rows, security
  classification matches security-origin text, and reboot status is the legacy
  reboot-file signal. These are existing heuristics, not comprehensive advisory
  coverage or proof that all processes run current binaries. Missing files do not
  establish portable no-reboot evidence for other managers. No security-only update
  or rollback guarantee is inferred. Existing behavior remains compatible.
- **DNF 4 / 5:** keep versioned command/output fixtures separate. A check with exit
  100 can mean updates are available, rather than an execution failure. Advisory
  absence, repository metadata failure and zero applicable advisories must be
  distinct. Transaction solving, module streams, exclusions and privilege checks
  need #48 evidence; never infer them from APT. Native DNF metadata and result
  parsing must be reviewed before reporting a known security count.
- **Zypper:** package updates, patches and distribution upgrades are different
  workflows. Do not equate Leap patch maintenance with a Tumbleweed distribution
  upgrade. Preserve informational result codes, including reboot-needed and
  package-manager-restart indications; neither authorizes an automatic reboot or
  blind retry. XML/structured-output, repository and solver cases belong to #48.
- **pacman:** the proposed official-repository workflow is a coherent full-system
  transaction. Single/selected routine upgrades must not create partial upgrades.
  Package details may be read-only; never translate an APT selection into a partial
  transaction. Repository synchronization, keyring and interrupted transaction
  handling require #49; AUR stays separate.
- **apk:** security evidence needs a matching release/repository advisory source;
  version differences alone do not classify security. Repository branches, pinned
  packages, configuration-file handling and reboot evidence need #51 verification.
- **Portage:** feasibility remains open. Ebuild/world/dependency/USE changes and GLSA
  coverage need their own collector and safety plan. Do not label no advisory
  match, an unresolved build or an absent Debian reboot file as a clean system.

These are requirements for future implementation, not newly installed command
handlers or claims of identical transaction/rollback behavior.

## Immutable observation contract and compatibility boundary

`linux/evidence.py` defines `ObservedValue`, `PackageEvidence` and
`InventoryEvidence`. A successful list has a nonnegative total, independently
qualified security count and reboot signal, and at most 50 unique package details.
Totals may exceed the shown subset. Per-package security may also lack evidence.
Known booleans and counts use strict types; `False` is not a count and `0` is not a
reboot result. Missing evidence requires a static reason code and a null value.
No raw provider text, exception, address or command is a reason code.

A failed list collection raises; it must not manufacture a successful empty list.
Keep any previous snapshot stale until authoritative replacement succeeds. The
evidence models perform no I/O. The #48 adapters project nullable observations
through guarded persistence, API and HA; their internal capability output uses v2,
while APT and Info strings remain compatible. Missing evidence stays explicit.

`from_legacy` preserves existing reported APT signal values and does not upgrade
heuristic provenance. `to_legacy` refuses conversion if security/reboot or any shown
package classification is missing. No `null → 0/false` fallback is permitted. Before
activating a non-APT provider, #48/#49/#51 must add compatible signal metadata and
UI/HA handling, or fail closed where v1 cannot express its results. Returning a
successful all-zero legacy snapshot is not a migration strategy.

## Reusable contract harness and required fixtures

`backend/tests/linux_contract_harness.py` injects manufactured module responses into
the actual executor/transport/application path. The same harness covers APT and the
independent full-only synthetic provider. It asserts initial counts/details, every
full/single/selected scope, measured post-update status, one privileged mutation,
no second cache refresh, no implicit reboot and unsupported-scope failure before
runner I/O. No process, SSH or managed-host action is executed.

`test_linux_matrix.py` additionally runs all family signal scenarios through the
neutral observation contract. Those fixtures **do not test native DNF/Zypper/pacman/
apk/Portage parsing or execution**; those adapters do not exist yet. It tests null
preservation, known zero/false, invalid/contradictory/oversized inputs, truncated
rows, strict types, immutability and refusal of lossy v1 conversion.

Before a future manager can be advertised, add at least:

1. Exact distro/manager/architecture provenance and wholly synthetic, bounded raw
   outputs for empty, ordinary, security and >50-row inventories; native parser
   tests must produce expected normalized evidence, not copied live data.
2. Manager-specific command result codes, malformed/truncated/changed formats,
   missing/incomplete advisory metadata, source mismatch and reboot unknown cases.
3. Safe full and eligible selected/single transactions, dependency effects, locks,
   stale plans, privileges, cancellation/timeout and ambiguous post-mutation reads.
   Refuse unsupported scope before mutation. Do not claim remote rollback or replay
   uncertain effects; retain original status as stale on read failure.
4. Existing API/UI/HA compatibility, visible unknown signals, authenticated policy,
   canonical locks, restart recovery and preserved IDs/configuration/SSH identity.
5. Complete `make release-check`, independent 95% line/branch coverage, both
   container architectures and the existing separate CI validators. Record exact
   unavailable real-platform checks; never substitute a fixture for certification.

## Primary references reviewed 2026-11-18

These upstream sources inform the requirements; they do not prove Commander
compatibility. They are read-only references, never fetched by tests or the app.

- [Debian APT maintenance](https://www.debian.org/doc/manuals/debian-faq/uptodate.en.html).
- [DNF 4 command reference](https://dnf.readthedocs.io/en/stable/command_ref.html) and
  [DNF 5 check-upgrade](https://dnf5.readthedocs.io/en/stable/commands/check-upgrade.8.html).
- [RHEL 9 DNF guide](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html-single/managing_software_with_the_dnf_tool/index),
  [Fedora 45 announcement](https://fedoramagazine.org/announcing-fedora-linux-45/).
- [openSUSE Zypper guide](https://doc.opensuse.org/documentation/tumbleweed/zypper/),
  [Zypper result-code reference](https://manpages.opensuse.org/Leap-16.0/zypper/zypper.8.en.html).
- [Arch maintenance / partial upgrades](https://wiki.archlinux.org/title/System_maintenance#Partial_upgrades_are_unsupported).
  The search excerpt was readable; direct page access was blocked by its anti-bot
  protection. No anti-bot control was bypassed.
- [Alpine apk handbook](https://docs.alpinelinux.org/user-handbook/0.1a/Working/apk.html),
  [release branches](https://www.alpinelinux.org/releases/),
  [Alpine security database](https://secdb.alpinelinux.org/).
- [Gentoo security and GLSA](https://security.gentoo.org/subscribe),
  [Portage emerge manual](https://github.com/gentoo/portage/blob/master/man/emerge.1).


## #48 native adapter implementation

See [ADR-0030](adr/0030-dnf-zypper-and-nullable-observations.md) for exact version/
manager admission, immutable native argv execution, unknown security data, Zypper
reboot signals, schema 15, API/HA compatibility and synthetic validation limits.
All other checklist requirements still apply. Full support is not inferred for
versions or architectures without separate evidence.

## Native sources follow-up

Auto now composes the detected system manager with available `flatpak_system`
and `flatpak_user` adapters. Explicit legacy providers retain system-only defaults;
manual source choices can add Flatpak independently. Full/single/selected Flatpak
updates preserve full native refs and installation scope. Named installations,
other desktop users, AUR, software installation/removal and unsupported distro/
manager combinations are excluded. Pacman admits manufactured Archlinux/CachyOS
profiles, requires preinstalled checkupdates, and supports full upgrades only.
No real OS/repository certification or new runtime dependency is claimed.
