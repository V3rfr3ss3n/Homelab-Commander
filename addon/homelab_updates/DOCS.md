# Homelab Updates app documentation

This app runs the native Homelab Updates backend and its management UI. It stores
the SQLite database, ED25519 identity and isolated `known_hosts` file under
`/data`; Home Assistant includes these files in app backups. The private key is
never available through the API or Ingress UI.

The app does not request host networking, the Docker socket, Home Assistant
configuration mounts or privileged capabilities. Shell custom tasks are disabled
by default.

## Installation

1. Open **Settings → Apps → App store → Repositories**.
2. Add `https://github.com/V3rfr3ss3n/Homelab-Commander`.
3. Install **Homelab Updates**.
4. Set a random API token of at least 32 characters in **Configuration**.
5. Keep shell tasks disabled unless their remote-code risk is explicitly accepted.
6. Start the app and open **Homelab Updates Backend** through Ingress.
7. Copy only the displayed public SSH key to a dedicated remote user.

Published release images are public and versioned; users do not enter GHCR
credentials. The app supports AMD64 and AArch64. If installation reports a GHCR
`401` or `403`, the maintainer has not completed publication of that exact
development version yet.

## Network access for the integration

Ingress needs no published host port. The Home Assistant integration must still
reach the backend REST API continuously, and this development version does not
automatically discover a stable Supervisor-internal hostname.

If no verified internal route exists, publish `8099/tcp` on an unused Home
Assistant host port and configure the integration with a reachable URL such as
`http://ha-host.example.invalid:8099`, replacing the reserved host with the
actual Home Assistant LAN address. The API token protects the endpoint, but HTTP
does not provide transport encryption. Keep it on a trusted network and never
expose it directly to the internet.

See the repository README for integration setup, host preparation, security and
removal instructions.
