---
title: SSH and Ansible execution
status: active
updated: 2026-10-31
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
