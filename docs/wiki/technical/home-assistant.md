---
title: Home Assistant integration
status: active
updated: 2026-10-31
tags: [wiki, technical]
---

# Home Assistant integration

The integration domain remains `homelab_updates`. Configuration uses HA-native
Config Entries, flows, reauthentication and reconfiguration. Typed `runtime_data`
owns the coordinator, services, provider adapters and task lifecycle.

## Schema compatibility

The integration uses HA's current Probatio schema engine where available, with a
small Voluptuous fallback for older supported installations. Both validation paths
are tested, including required-field rejection. An unrelated import failure is
not swallowed. Device classes similarly use the current explicit exports with
narrow fallbacks to older public exports. No schema package is added to users'
manifest requirements.

## Status and entities

A shared DataUpdateCoordinator obtains a single host snapshot per poll. Network
I/O is asynchronous through HA's injected shared HTTP session. Entity descriptions,
translation keys, device classes and stable technical IDs follow native HA patterns.
New hosts are registered dynamically. Existing temporarily absent hosts retain
identity and become unavailable.

## Commands and lifecycle

Application services route deliberate actions to provider protocols. Tracking has
bounded deadlines, unknown-state handling and cancellation on unload. Terminal
completion removes active trackers before the final listener notification and
requests status refresh on success.

## Native panel

The administrator-only panel uses HA's authenticated WebSocket connection, not a
browser copy of the backend token. Status subscriptions carry compact host/job
metadata. Logs are fetched explicitly by a separate admin-only command and rendered
as text. Neither browser storage nor recorder/diagnostics receives full job output.
With multiple native entries, the first loaded owns the global panel; unloading it
hands ownership to another loaded native entry.

## Local discovery and compatibility

Optional Supervisor metadata discovery matches both App slug and repository identity,
derives the internal endpoint and validates health/token. Missing or incompatible
local Apps retain manual remote setup. Existing remote entries are not rewritten.
A discovered local **Manage backend** link uses the HA App route in the same tab.

Legacy entries migrate without changing established entity identities. Provider
JSON stays in adapters. See [ADR-0009](../../02-architecture/adr/0009-supervisor-native-backend-discovery.md)
and [requirements](../../01-product/requirements.md) before changing this contract.
