---
title: ADR-0009 Supervisor Native Backend Discovery
status: accepted
date: 2026-08-23
tags: [architecture, home-assistant, discovery, security]
---

# ADR-0009: Supervisor Native Backend Discovery

## Context

The Home Assistant App DNS identifier contains a repository-specific component.
Asking users to discover and transcribe it makes a local installation needlessly
fragile. The integration must still support Home Assistant Container/Core and
remote native backends.

## Decision

On a Home Assistant OS or Supervised instance, the integration uses Home
Assistant's managed Supervisor client to list installed Apps. It accepts an App
only when both its stable `homelab_updates` slug and normalized public repository
identity match. If `/addons` exposes the installation-specific repository ID,
the integration resolves it through the read-only Supervisor repository metadata
and compares its public source URL. It derives the internal DNS name from the returned identifier by
replacing underscores with hyphens and validates `/api/v1/health` before the
normal token/API validation succeeds.

For the Home Assistant operational panel, the same discovered App identifier is
also used for the local `/app/<identifier>` frontend route. **Manage backend**
therefore opens Supervisor Ingress in the current Home Assistant tab, like the
App page's own **Open UI** action. A remote backend keeps its explicit external
URL and opens in a separate tab.

Supervisor access is optional (`after_dependencies: hassio`). Missing,
unavailable, stopped, or incompatible Apps fall back to the existing manual
remote URL flow. Existing native entries retain their stored URL until a user
explicitly reconfigures them. No Supervisor credential, App option, or API token
is read or exposed.

## Consequences

- Local users no longer need an internal hostname or port during setup.
- Remote and standalone deployments remain supported.
- Product branding becomes **Homelab Commander**, while `homelab_updates`, the
  App slug, Python module, config-entry identities, and `/api/v1` stay stable.
- The integration deliberately depends only on Supervisor App metadata, not on
  mutable display names.

## References

- [Supervisor API endpoints](https://developers.home-assistant.io/docs/api/supervisor/endpoints/)
- [App communication](https://developers.home-assistant.io/docs/apps/communication/)
