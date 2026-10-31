---
title: Installation
status: active
updated: 2026-10-31
tags: [wiki, user-guide]
---

# Installation

## Choose a deployment

The recommended Home Assistant OS/Supervised deployment uses two components:

| Component | Install through | Purpose |
| --- | --- | --- |
| Homelab Commander | HACS, as an Integration | Devices, entities, config flow and direct backend UI sidebar entry |
| Homelab Commander Backend | Home Assistant App store | Host inventory, SSH/Ansible, persistent jobs and administrative UI |

Home Assistant Container/Core users run the backend separately and configure the
integration with its reachable URL. The backend can also run without the
integration when only its management UI or external API is needed.

## Home Assistant OS or Supervised

1. Add `https://github.com/V3rfr3ss3n/Homelab-Commander` to HACS as an
   **Integration** custom repository. Install **Homelab Commander** and restart HA.
2. Add the same repository under **Settings → Apps → App store → Repositories**.
   Install **Homelab Commander Backend**.
3. Set a random API token of at least 32 characters in the App options. Keep shell
   tasks disabled unless you explicitly accept their privileges.
4. Start the App and open its authenticated Ingress UI.
5. Complete [host onboarding](hosts.md), then add the integration under
   **Settings → Devices & services → Add integration**.
6. Select the native backend. A compatible running local App is discovered on
   OS/Supervised; enter its API token. No internal hostname or repository ID is
   required.

The App image is versioned and must be anonymously pullable. A registry login is
not a workaround for a failed public image release.

## Standalone Docker

Use the repository's `compose.yaml` and read the token interactively:

```bash
read -rsp 'Backend API token: ' HUL_API_TOKEN
export HUL_API_TOKEN
docker compose config --quiet
docker compose up --build --detach
```

The supplied Compose file binds the UI/API to loopback on port `8099`. Persistent
data is held in its named volume. To access it from another machine, deliberately
configure a trusted network binding or HTTPS reverse proxy and firewall rules.
Do not commit a token or deployment-specific Compose copy.

Next: [configuration](configuration.md). Release verification is documented in
the [installation checklist](../../04-operations/public-install-checklist.md).
