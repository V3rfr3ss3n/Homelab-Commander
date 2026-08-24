# Homelab Commander

Home Assistant-native homelab management for Linux hosts, jobs, automation and
remote operations. Software updates are the first mature capability; the
architecture is designed to grow beyond update management.

> [!WARNING]
> Version `0.3.0-dev.0` is a development release. Use it in a test environment
> first and keep backups of the backend `/data` volume.

## Two components, one Native setup

| Component | Name in Home Assistant | Responsibility |
| --- | --- | --- |
| HACS custom integration | **Homelab Commander** | Config flow, devices, entities, diagnostics and the operational sidebar panel |
| Home Assistant App | **Homelab Commander Backend** | FastAPI backend, SQLite, Ansible/OpenSSH, persistent jobs, SSH identity and Ingress management UI |

The App manages hosts; the integration represents their state and controls in
Home Assistant. Install both for the recommended Native experience.

## Installation

1. In HACS, add `https://github.com/V3rfr3ss3n/Homelab-Commander` as an
   **Integration** custom repository, install **Homelab Commander**, then restart
   Home Assistant.
2. In **Settings → Apps → App store → Repositories**, add the same repository.
   Install and start **Homelab Commander Backend**.
3. Configure a random API token of at least 32 characters in the App. Keep shell
   tasks disabled unless their risk has been explicitly accepted.
4. Open the App through its authenticated Ingress entry, copy its public SSH key
   to the dedicated target user, add a host, then test the connection.
5. In **Settings → Devices & services → Add integration**, select
   **Homelab Commander → Homelab Commander Backend** and enter the same API
   token. On Home Assistant OS and Supervised, a running compatible local App is
   discovered automatically; no repository identifier, hostname, port or URL is
   required.

Home Assistant Container, Core/dev installations, and standalone or remote
backends retain the explicit **Remote / standalone backend** option. Enter a
reachable URL and the API token in that flow. Existing remote configurations are
preserved and are never silently replaced by local discovery.

## Security model

- API access requires a constant-time checked Bearer token.
- The integration stores that token only in its Home Assistant config entry; it
  is never taken from Supervisor, logged, added to diagnostics or entity data.
- The standalone UI exchanges its token for a short-lived HttpOnly session and
  never persists it in browser storage.
- The private SSH key, authorization headers and configuration dictionaries are
  never returned or logged.
- Updates and reboots are distinct, explicit actions. Shell tasks are disabled
  by default and command tasks use argument arrays without shell interpretation.

Read the [security and privacy model](docs/04-operations/security-and-privacy.md)
before granting passwordless sudo.

## Operations and architecture

The native backend runs identically as a Home Assistant App or standalone
container. It persists hosts, jobs, custom tasks, its ED25519 identity and
isolated `known_hosts` data under `/data`. Home Assistant never runs Ansible and
never receives the private key.

See the [native backend guide](docs/04-operations/native-backend.md),
[public-install checklist](docs/04-operations/public-install-checklist.md) and
[architecture overview](docs/02-architecture/overview.md). The optional
Semaphore provider remains available for compatible legacy installations.

## Compatibility identifiers

The user-facing product is **Homelab Commander**. Existing installations remain
compatible: the Home Assistant domain and App slug are still `homelab_updates`,
the Python module remains `homelab_updates`, and the native API remains
`/api/v1`. Do not use those technical identifiers as a product name.
