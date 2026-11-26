---
title: DNF and Zypper maintenance with nullable observations
status: proposed
updated: 2026-11-18
tags: [architecture, linux, providers, migration, compatibility, security]
---

# ADR-0030: DNF/Zypper and nullable observations

## Scope and dependencies

Issue #48 builds on the #47 contracts (review branch `feat/linux-capability-matrix`,
!44 / PR #74). This is a stacked review branch; #47 has not been merged by this
implementation. Keep `/api/v1`, Host/resource/job IDs, SSH identity, HA configuration,
central policy, immutable scopes, conflicts and never-replay recovery. No new
production dependency, collection, framework, credential or implicit action.

Static provider composition adds `dnf` and `zypper`. Existing `debian_apt` and valid
APT full/single/selected behavior remain. The Linux feature's inventory-provider
Protocol owns native collection/application through the injected module runner;
the shared core contains no DNF/Zypper dispatch cases. Native adapters are stateless
across hosts and use immutable normalized observations. Capability bindings use
internal v2 qualified output for these adapters; APT keeps its v1 binding. Legacy
Info capability strings and public endpoint paths remain unchanged. Assessment
alone performs no I/O and grants no authority.

## Admission and supported operations

- DNF: Fedora 45 with detected `dnf5`; RedHat/Rocky/AlmaLinux major 9 with detected
  `dnf`/`dnf4`. Fail before privilege/metadata calls for unknown combinations.
- Zypper: openSUSE Leap 16.0 supports regular package full/single/selected updates.
  Tumbleweed supports inventory/reboot observations only, with empty observed
  update scopes; reject mutations before any command. No rolling `dist-upgrade`,
  version migration, patch-only update or vendor-switch workflow is activated.
- Configuration is explicit in the existing Host dialog/API. Facts detect the
  configured family's actual manager/version; there is no automatic provider
  discovery or silent substitution. A provider change invalidates old package
  evidence and task checks while preserving the Host UUID.
- Before package operations, validate root execution with a fixed `id -u` probe
  through existing non-interactive become. No password prompt, user setup, package
  bootstrap, helper installation or privilege escalation beyond existing configured
  maintenance authority. SSH onboarding templates remain Debian/Ubuntu only; RPM
  hosts need independently prepared SSH/Python/sudo access.

Candidate versions are narrow admitted profiles, not OS certification. Tests use
manufactured native outputs. Exact deployed version/repository/architecture evidence
remains an operator/platform acceptance task, never an automated managed-host test.

## Native adapters and transaction safety

Use core Ansible setup/command only. A fixed Python script runs an explicit argv
with C locale, closed stdin, bounded in-memory output capture and fixed deadlines.
Excess output is drained without retaining it; it does not abort a mutation merely
to enforce the capture limit, but causes a safe failed observation afterward. It uses
no shell, imports no manager bindings and installs no missing dependencies. Target
requirements are Python 3 compatible with the pinned Ansible core, sudo/become,
RPM and the native manager; DNF also needs
working `repoquery`. The script returns native stdout/exit status for adapter-only
validation. Raw output, repository URLs and exception text are never forwarded into
these adapters' job logs or errors; diagnostics retain static operation/code/status.
Pipes and selectors are closed on all paths. A remote child can outlive transport
interruption; the existing uncertain-mutation/no-replay rules remain essential.

DNF refreshes metadata explicitly, queries upgrade candidates using formatted
name/architecture/EVR records and latest limits, and reads installed versions only
for the bounded detail subset. Mutations use native `upgrade`, never `install`,
`--allowerasing` or disabled signature verification. Zypper refreshes metadata and
parses bounded XML package-update records, rejecting malformed/entity-bearing/error
payloads. It executes regular `update`, never `dist-upgrade`, force resolution or
automatic key import. Native solver/exclusion/dependency behavior remains; a
successful command does not promise every candidate was installed.

Architecture-qualified names are frozen in the existing job scope. The shared
identifier envelope admits safe ASCII uppercase/underscore needed by RPM; provider
validation preserves APT's narrower grammar and checks RPM selections against a
fresh eligible inventory. No glob, whitespace, option, shell expression or silent
scope widening. Readiness is revalidated at dispatch. A full or scoped mutation is
invoked at most once by this workflow, followed by a fresh measured inventory.

Zypper result 102 is a reboot hint, retained even if an immediate probe disagrees.
Result 103 ends the job with an explicit reviewed-reinvocation error; no automatic
second mutation. Ordinary failure, timeout, malformed output and post-update read
failure fail the job and preserve prior package counts marked stale. There is no
remote rollback, transaction undo, automatic retry or implicit reboot. Schema
rollback tests refer to local migration atomicity, not remote package rollback.

## Missing security/reboot evidence and compatibility

Both initial native adapters deliberately report security classification **unknown**;
no advisory-coverage claim or security-only operation is exposed. Missing metadata
is never zero and package rows use `is_security: null`. DNF restart status is unknown
until a separately reviewed collector exists. Zypper `needs-rebooting` maps 0/102
to native false/true; unsupported/failing probes produce unknown. This is a native
signal, not proof that every process uses current binaries.

Schema 15 adds `security_known`, `reboot_known` and `package_scopes_json` without
rewriting old values or IDs. Existing rows default to known legacy signals. Unknown
values use guarded storage placeholders; repository reads and group projections
respect the flags, so placeholders never become public zero/false observations.
Explicit unknown host/package responses use JSON null in the existing security/
reboot fields; `package_scopes` is additive. Valid APT responses retain their values.

This extends the field types for **new RPM configurations**. Update the integration
before enabling these providers. Updated HA parsing retains null, sensors/binary
sensors show unknown, the update summary names missing security evidence, and a
previous reboot repair remains until an explicit false observation clears it.
Older integration versions may reject new RPM observations and become unavailable;
that is safer than a false healthy value. Existing APT-only installations keep
working. Third-party strict clients must adopt the nullable fields/additive scope
metadata before consuming new providers.

The UI shows unknown security/restart states in rows, details, package dialog,
notices and aggregate labels. It disables unobserved/unsupported package scopes and
excludes read-only targets from bulk updates. Backend admission remains authoritative.
Provider changes clear incompatible cached details; failed checks/updates retain
measured counts as stale. The disposable preview simulates RPM observations/actions
without importing or falling back to a real executor.

## Migration, validation and limits

DDL and schema marker share the existing atomic transaction; test schema-14 data,
known bits, UUID preservation, null round trips and rollback of all new columns.
Back up `/data` before deployment. Do not downgrade an RPM-enabled database to an
older backend/integration: older code cannot interpret the evidence flags. Restore
an appropriate pre-upgrade backup instead. This PR performs no real installation,
downgrade, managed-host action, release, tag or merge.

Tests cover native scope/result/code/privilege cases, malformed and bounded output,
unknown signals, API/worker failures/recovery, no retry/rollback/reboot, additive
migration, HA states/repair and real Chromium Standalone/nested Ingress. Full
release-check and independent 95% line/branch gates remain required. Container
runtime checks certify Commander packaging, not Fedora/RHEL/openSUSE installations.

## Primary references reviewed 2026-11-18

- [DNF 4 command/query reference](https://dnf.readthedocs.io/en/stable/command_ref.html).
- [DNF 5 repoquery](https://dnf5.readthedocs.io/en/stable/commands/repoquery.8.html).
- [RHEL 9 DNF guide](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html-single/managing_software_with_the_dnf_tool/index).
- [Zypper manual and result codes](https://manpages.opensuse.org/Tumbleweed/zypper/zypper.8.en.html).
- [Zypper upstream command documentation](https://github.com/openSUSE/zypper/blob/master/doc/zypper.8.txt).

- [Pinned-core Python support matrix](https://docs.ansible.com/projects/ansible/latest/reference_appendices/release_and_maintenance.html).
