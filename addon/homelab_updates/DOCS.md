# Homelab Updates Backend App

This App is one half of the recommended Native installation. It provides the
FastAPI backend, SQLite persistence, Ansible/OpenSSH execution, persistent jobs,
the managed ED25519 identity and the **Homelab Updates Backend** Ingress UI.

It does not create Home Assistant entities, devices or the operational
**Homelab Updates** panel. Those belong to the separate HACS integration. Install
both components by following the
[public installation guide](https://github.com/V3rfr3ss3n/Homelab-Commander#installation).

The App stores its database, ED25519 identity and isolated `known_hosts` file
under `/data`; Home Assistant includes these files in App backups. The private
key is never available through the API or Ingress UI.

The App does not request host networking, the Docker socket, Home Assistant
configuration mounts or privileged capabilities. Shell custom tasks are disabled
by default.

## Installation

1. Install the **Homelab Updates** integration through HACS and restart Home
   Assistant.
2. Open **Settings → Apps → App store → Repositories**.
3. Add `https://github.com/V3rfr3ss3n/Homelab-Commander`.
4. Install **Homelab Updates Backend**.
5. Set a random API token of at least 32 characters in **Configuration**.
6. Keep shell tasks disabled unless their remote-code risk is explicitly accepted.
7. Start the App and open **Homelab Updates Backend** through Ingress.
8. Copy only the displayed public SSH key to a dedicated remote user.
9. Configure the HACS integration with the same token and a reachable backend URL.
10. Use the integration's **Homelab Updates** panel for daily operation.

Published release images are public and versioned; users do not enter GHCR
credentials. The App supports AMD64 and AArch64. If installation reports a GHCR
`401` or `403`, the maintainer has not completed publication of that exact
development version yet.

## Network access for the integration

Ingress itself needs no published host port. On Home Assistant OS and Supervised,
Home Assistant Core can normally reach Apps by their generated internal DNS name.
Run `ha addons list` in a Home Assistant terminal and locate the full installed
App identifier. For an identifier `<repository-id>_homelab_updates`, configure:

`http://<repository-id>-homelab-updates:8099`

The repository identifier is installation-specific. Do not copy one from another
installation. The API token remains required even on the internal network.

If that internal name is unavailable, publish `8099/tcp` on an unused Home
Assistant host port and use a reachable LAN URL. The external API is protected by
the token, but plain HTTP does not provide transport encryption. Keep it on a
trusted network and never expose it directly to the internet. A Supervisor
Ingress URL is a browser route and is not a backend API URL.

Read the
[full operations guide](https://github.com/V3rfr3ss3n/Homelab-Commander/blob/main/docs/04-operations/native-backend.md)
for host preparation, backup, security and removal instructions.
