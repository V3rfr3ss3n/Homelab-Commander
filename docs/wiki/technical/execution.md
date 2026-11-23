---
title: SSH and Ansible execution
status: active
updated: 2026-11-23
tags: [wiki, technical]
---

# SSH and Ansible execution

Only the backend executes remote operations. The integration never opens SSH or
starts Ansible. The execution adapter uses structured argument lists and an
isolated one-host inventory per operation. Built-in commands use the same
`auto_silent` Python discovery strategy; no fixed interpreter path is assumed.

## Result contract

A private Ansible callback produces exactly one validated JSON result envelope.
The adapter separately checks process exit status, module event and payload shape.
Success needs exit `0`, an `ok` event and valid structured result. Warnings and stderr
remain bounded job output; free text is not parsed as a successful domain response.

## Connection test

The explicit test verifies SSH, minimal Python/distribution/kernel facts and
non-interactive sudo using a harmless privileged command. It does not install
packages or reboot. The interpreter is detected per isolated run rather than stored
as a potentially stale fixed path.

## APT status check

1. Read minimal facts.
2. Refresh APT metadata through `ansible.builtin.apt` with privilege escalation.
3. Read `/usr/bin/apt list --upgradable` with `LC_ALL=C`/`LANG=C`, without a shell.
4. Check `/var/run/reboot-required` with `ansible.builtin.stat`.

Zero packages/security updates, unchanged cache and no reboot file are successful
outcomes. Phase-specific errors and safe interpreter/sudo/lock categories provide
useful UI messages without exposing raw process output.

The package provider models package operations, not transport. Further package
managers belong behind that boundary. Custom command tasks use argv; shell tasks
are explicit deployment-level opt-ins. See the [operations reference](../../04-operations/native-backend.md).

## Controller paths in unprivileged containers

Every invocation sets `ANSIBLE_HOME`, `ANSIBLE_LOCAL_TEMP` and
`ANSIBLE_SSH_CONTROL_PATH_DIR` inside its private temporary working directory.
This prevents inherited root-home defaults from directing controller writes or
SSH control sockets to `/root/.ansible` after the container drops privileges.
Directories are isolated between invocations and removed on completion or failure.
Persistent SSH identity and `known_hosts` remain in the backend data directory.
No remote permissions or SSH/sudo policy are changed.


SSH execution explicitly disables TTY allocation, matching the guided setup's
non-interactive, no-PTY key restrictions. Maintenance still requires deliberately
provisioned non-interactive sudo; no credential prompt is used.


## Linux distribution and signal evidence

APT remains the only production package provider. The
[Linux matrix](../../02-architecture/linux-provider-matrix.md) lists candidate
versions and supported/unsupported/unknown operation cases separately from actual
platform evidence. DNF/Zypper/pacman/apk/Portage fixtures exercise missing-evidence
semantics; they do not claim native parsing or execution support. Pacman partial
upgrades and AUR execution are not exposed.

Internal immutable evidence models preserve unknown, unavailable and unsupported
security/reboot signals as null with a safe reason. Known zero/false needs actual
collector evidence. The legacy bridge rejects missing data instead of silently
reporting a clean host. Existing APT signal heuristics and `/api/v1` remain unchanged;
future providers must add compatible API/UI/HA handling before activation. See
[ADR-0029](../../02-architecture/adr/0029-linux-evidence-and-compatibility-matrix.md).


## Native RPM maintenance (#48 review)

The dependent #48 branch statically registers DNF and Zypper adapters. Fedora 45
requires detected dnf5; RHEL/Rocky/AlmaLinux 9 require dnf/dnf4. Leap 16.0 supports
regular package full/single/selected updates; Tumbleweed is inventory-only. Version/
manager mismatch and unsupported scopes fail before privileged mutation.

Fixed argv calls use the existing SSH runner, non-interactive root verification,
bounded output and deadlines. Nothing installs prerequisites, imports repository
keys, disables signature checking, executes a rolling distribution upgrade, retries
a mutation or reboots. Security classification is explicitly unknown; DNF reboot
is unknown, Zypper uses its own 0/102 signal. A 103 result requires human review of
another invocation. A post-update read measures remaining counts; failure preserves
old counts as stale without remote rollback. See
[ADR-0030](../../02-architecture/adr/0030-dnf-zypper-and-nullable-observations.md).

## Multi-source native maintenance (review)

The Linux adapter composes one system manager with optional system/SSH-user Flatpak
sources. Exact native refs are freshly validated for selected operations. Sources
run serially under the existing host lock; no Pamac duplicate, own package database,
lock removal, signature bypass, implicit reboot or action replay is introduced.
A later failure uses `package_sources_partial_failure` and retains stale measured
state until native recheck. Aggregate refresh failure cannot imply whole-host
success. Pacman permits full upgrades only; Flatpak retains installation scope.
See [ADR-0032](../../02-architecture/adr/0032-native-package-sources-without-catalog.md).
