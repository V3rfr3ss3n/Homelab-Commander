---
title: Purpose and scope
status: active
updated: 2026-10-31
tags: [wiki, product]
---

# Purpose and scope

Homelab Commander is an extensible HA-native interface for local homelab operations.
Linux update management is its first mature capability. The product aims to make
host state understandable and explicit actions predictable without turning HA
into a privileged execution engine.

## Component responsibilities

HA provides configuration, devices, entities, diagnostics and the operational panel.
The native backend owns inventory, SSH identity, SQLite persistence and execution.
The App packages that backend for Supervisor/Ingress; standalone Docker runs the
same application. Semaphore remains an optional legacy provider.

## Current capability

- Dynamic Linux host status and native update/reboot controls.
- Native asynchronous jobs, explicit log inspection and custom tasks.
- UI configuration, reauthentication, reconfiguration and provider migration.
- Administrative backend UI and administrator-only HA operational panel.
- Built-in Debian/Ubuntu APT checks and controlled maintenance operations.

## Deliberate limits

No implicit updates or reboots, direct SSH/Ansible execution inside HA, built-in
package-by-package management, or autonomous maintenance scheduler. Windows,
container image updates, VM lifecycle, snapshots and backup orchestration are
not established current capabilities. The architecture allows future capabilities
through bounded services and providers rather than a universal manager.

Technical compatibility identifiers remain `homelab_updates` and `/api/v1` even
though the product name is Homelab Commander.

Normative detail: [vision](../../00-project/vision-and-scope.md) and
[requirements](../../01-product/requirements.md). These remain versioned project
records rather than a promise that every roadmap item is implemented.
