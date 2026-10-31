---
title: ADR-0010 Secure test dependency replacements
status: accepted
updated: 2026-10-31
tags: [architecture, security, dependencies, testing]
---

# ADR-0010: Replace vulnerable development dependencies with tested fixed pins

## Context

The owner requested resolving dependency findings so the modernization MR can
merge. The old HA 2026.8 test graph pins vulnerable cryptography and other packages.
HA 2026.10.4 fixes those core pins but still requires Pillow 12.3.0; Pillow 13.0.0
contains the relevant security fixes. Extending the expired exception or ignoring
advisories would preserve the problem. A global unreviewed override is unacceptable.

## Decision

Update the development baseline to HA 2026.10.4, its declared frontend version and
the matching custom-component test plugin. Refresh the reproducible transitive lock.
Use one explicit uv replacement: `pillow==13.0.0`, with a comment pointing here.
Pillow is used by the HA development environment and is absent from the backend's
production dependency graph. The integration adds no manifest requirements and does
not replace dependencies on users' HA installations.

This replacement is not a vulnerability exception: the fixed package is installed
and remains subject to the unfiltered audit. Review its release notes and verify
our complete supported HA integration/lifecycle and browser surface, plus image
loading/resizing through HA's image utility. This does not certify all HA Core
integrations with a modified Pillow pin.

Remove the replacement when a subsequently tested HA release accepts a fixed
Pillow version itself. Review it on every HA dependency update; do not add further
replacements without a specific security/compatibility rationale and regression
coverage. The owner of this maintenance is the project maintainer.

Remove resolved SE-2026-001 from the active expiry registry and all three audit
ignores. Preserve its historical record as resolved. Production cryptography comes
from the same lock; remove the Docker post-sync installation that diverged from it.

The HA upgrade also changes the framework schema engine. A small infrastructure
compatibility module uses Probatio on the current baseline and Voluptuous when
Probatio is absent, retaining the existing minimum HA version without adding
manifest dependencies. Test both required-field validation paths and propagate
unrelated import failures. Device classes use their explicit framework modules.

## Consequences

The local/CI environment intentionally differs from upstream's Pillow pin, and we
own testing that difference. Full tests and an unfiltered audit must be green before
merge; the production-only graph must be audited independently and contain no
Pillow/HA/test tools. No coverage or security thresholds are reduced. Existing
configuration, API, SSH identity and persistence contracts stay unchanged.

## Sources

- [HA 2026.10 release notes](https://www.home-assistant.io/blog/2026/10/07/release-202610/)
- [HA 2026.10.4 dependency metadata](https://pypi.org/pypi/homeassistant/2026.10.4/json)
- [Pillow 13 security and compatibility notes](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html)
