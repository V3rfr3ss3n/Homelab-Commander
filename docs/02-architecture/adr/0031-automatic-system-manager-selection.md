---
title: Automatic system package-manager selection
status: proposed
updated: 2026-11-22
tags: [architecture, linux, providers]
---

# ADR-0031: Automatic system manager selection

## Decision

Default the new-host UI to `auto`; preserve the legacy API omission default
(`debian_apt`) for existing clients, explicit provider configurations
and stored identities. Resolve validated Ansible distribution and manager facts
inside the existing adapter boundary when an explicit job runs. Delegate to APT
for Debian/Ubuntu with apt, DNF for its admitted profiles, or Zypper for its admitted
profiles. Never fall back to another manager following failure or discover by
mutation. Unknown facts fail safely. A single action applies once and then reads
fresh observations. No new dependencies, permissions or data migration are needed.

Observed scopes remain unknown before discovery; a successful APT detection adds
explicit scopes, and RPM providers preserve their existing scope restrictions.
A host-wide system package manager remains distinct from future independent
package sources. Do not model multiple independent sources as competing system
managers: each source will need its own identity, inventory, freshness, scopes
and immutable job targeting before combined actions can be safely offered.

## Consequences and evidence

Existing APT configurations behave as before. Detection never means scheduled
updates or reboots. Unknown security/reboot evidence remains unknown. All tests
use manufactured facts and injected runners; no real host certification is claimed.
Standalone and Ingress browser checks cover explicit and automatic RPM selection.
Source publication and merge/release remain separate review steps.
