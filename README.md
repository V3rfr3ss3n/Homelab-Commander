# Homelab Updates

Homelab Updates manages Linux update operations from Home Assistant. It combines
a Home Assistant custom integration with a separate native backend that connects
to managed hosts through SSH and Ansible.

> [!WARNING]
> Version `0.2.0-dev.1` is a development release. Use it in a test environment
> first and keep backups of the backend `/data` volume.

## Two components, one Native setup

The recommended Native setup requires both installable components:

| Component | Name in Home Assistant | Responsibility |
| --- | --- | --- |
| HACS custom integration | **Homelab Updates** | Config flow, devices, entities, update/reboot controls, diagnostics and the operational sidebar panel |
| Home Assistant App | **Homelab Updates Backend** | FastAPI backend, SQLite, Ansible/OpenSSH, persistent jobs, SSH identity and the management Ingress UI |

The App alone does not create Home Assistant entities. The HACS integration alone
does not contain or run the native Ansible backend. Install both for the
recommended Native experience. Their two sidebar entries are intentionally
different: use **Homelab Updates Backend** to onboard hosts and use
**Homelab Updates** for daily operation.

## What it does

- shows Debian and Ubuntu hosts in Home Assistant;
- checks normal and security updates;
- installs updates only after an explicit user action;
- keeps reboot separate and requires an explicit request;
- records persistent job history with bounded, redacted logs;
- provides an administrator-only Home Assistant overview and management UI;
- supports structured command tasks, with shell tasks disabled by default;
- keeps SSH inventory, jobs and the private key in the native backend.

Home Assistant never runs Ansible itself and never receives the private SSH key.
Semaphore remains available as an optional legacy provider.

## Installation

### Recommended installation

The integration and the Home Assistant app use the same public repository:

`https://github.com/V3rfr3ss3n/Homelab-Commander`

1. In HACS, open **Integrations → Custom repositories**, add the repository URL
   as category **Integration**.
2. Install **Homelab Updates** from HACS.
3. Restart Home Assistant after HACS finishes installing the integration.
4. Open **Settings → Apps → App store → Repositories** and add the same
   repository URL.
5. Install **Homelab Updates Backend**, then open its **Configuration** tab.
6. Generate a random API token with at least 32 characters outside this
   repository, enter it as `api_token`, keep shell tasks disabled, and start the
   App.
7. Open **Homelab Updates Backend** through its authenticated Ingress sidebar.
8. Copy the displayed public SSH key to the dedicated target user's
   `authorized_keys`, add the host, and run **Test connection**.
9. Make the backend API reachable as described below. Open
   **Settings → Devices & services → Add integration**, select
   **Homelab Updates → Native backend**, and enter that URL and the same token.
10. Use the **Homelab Updates** integration panel for daily host, update and job
    operation; return to **Homelab Updates Backend** for host onboarding and
    backend administration.

There is no zero-configuration discovery in this development version.

### Does port 8099 need to be exposed?

Ingress itself does not need a published port. The Home Assistant integration,
however, must reach the backend REST API continuously. This version does not
discover a stable Supervisor-internal app hostname automatically.

On Home Assistant OS and Supervised installations, Core can normally reach the
App through the internal app network without publishing a host port. Run
`ha addons list` in the Home Assistant terminal and locate the full installed App
identifier. If it is `<repository-id>_homelab_updates`, use:

`http://<repository-id>-homelab-updates:8099`

as the Native backend URL, replacing underscores with hyphens exactly as shown.
The repository identifier is generated from the repository URL and must never be
copied from another installation or hardcoded in this project. Keep the port
mapping disabled when this URL works. The API still requires the configured
Bearer token.

If the internal name is unavailable in a particular installation, use this LAN
fallback:

1. Open the app's **Network** settings.
2. Publish `8099/tcp` on an unused Home Assistant host port.
3. Use a URL reachable from Home Assistant Core, for example
   `http://ha-host.example.invalid:8099`, replacing the reserved example host
   with your Home Assistant host's actual LAN address.

The published external API is protected by the API token but does not provide TLS.
Restrict it to a trusted network and never expose it directly to the internet.
If you already have a trusted reverse proxy or a verified Supervisor-internal
route, you may use that instead and leave the host port disabled.

### Supported systems

The built-in package provider currently supports:

- Debian;
- Ubuntu;
- other compatible APT-based systems after testing.

DNF, Pacman, APK and other package managers are future work.

## First host setup

Use a dedicated automation account on each managed host. The backend-generated
ED25519 private key remains under the app's persistent `/data` directory; only
the public key belongs on target hosts.

**Test connection** verifies SSH, Python 3 discovery, Linux facts and
non-interactive sudo. Ansible modules execute temporary Python code, so a broad
rule such as `NOPASSWD: ALL` effectively makes the backend key a privileged
machine identity. Protect that key, restrict its network access and use the
narrowest privilege design your environment can support.

After onboarding, run **Check hosts** before using update actions. An update can
report that a reboot is required, but it never starts the reboot automatically.

## Security model

- API access uses a constant-time checked Bearer token.
- Standalone UI login exchanges the token for a short-lived opaque HttpOnly
  session; the token is not stored in browser storage or cookies.
- Ingress relies on Supervisor authentication and CSRF protection.
- The private ED25519 key, Authorization headers and configuration dictionaries
  are never returned or logged.
- Job output is bounded, removes NUL bytes and redacts the selected host address
  and remote user.
- Job logs stay behind authenticated API, session, Ingress or administrator-only
  Home Assistant access.
- Update and reboot remain separate explicit actions.
- Command tasks use argument arrays without shell interpretation. Shell tasks
  require a visible deployment-wide opt-in and are disabled by default.

Read the complete [security and privacy model](docs/04-operations/security-and-privacy.md)
before granting passwordless sudo.

## Home Assistant experience

Each host exposes update state, normal and security update counts, distribution,
kernel, last check and reboot requirement. Native installations also expose
backend connectivity, queued/running jobs, latest job and the latest historical
failure as separate states.

Administrators receive a **Homelab Updates** sidebar panel for the operational
overview. **Open log** retrieves one bounded log on demand through Home Assistant
authentication. **Manage backend** opens the configured browser-reachable
backend URL; the separate **Homelab Updates Backend** entry opens the app's
Ingress management page.

## Troubleshooting installation

### App installation reports GHCR denied

The app requires the public image
`ghcr.io/v3rfr3ss3n/homelab-updates-backend:0.2.0-dev.1`. A `401` or `403`
means that this exact image version has not been published publicly yet. Users
must not log in to GHCR; the maintainer must complete the documented publication
and one-time package-visibility step.

### HACS shows a placeholder icon

The repository contains valid local Home Assistant brand assets. A placeholder
on a HACS repository card does not affect installation and can lag behind the
installed integration because repository presentation and frontend caches are
separate. There is no external branding URL in `hacs.json`, and Home Assistant
2026.3 or newer can serve the bundled custom-integration brand directly.

### Integration cannot connect to the app

Do not enter a Supervisor Ingress URL as the backend URL. Use the generated
internal App hostname described above, publish the API port as a LAN fallback, or
provide another route that Home Assistant Core can reach. Use the same API token
configured in the App.

## Standalone Docker

The same backend image can run without Home Assistant:

1. Export a random token as `HUL_API_TOKEN`.
2. Start the hardened Compose example:

   ```bash
   docker compose up --build --detach
   ```

The sample binds only to `127.0.0.1:8099`, drops Linux capabilities, enables
`no-new-privileges`, uses a read-only root filesystem and stores persistent
state in `homelab-updates-data`. See the
[native backend operations guide](docs/04-operations/native-backend.md) for
reverse-proxy, backup, SSH and failure-handling details.

## Architecture

```text
Home Assistant entities and config flow
                 |
       provider-neutral protocols
          /                  \
 native REST client       Semaphore adapter
          |                  + status adapter
 native backend
 API → services → SQLite queue → Ansible → one selected host
          |
 App Ingress UI or standalone Docker
```

The integration, backend and app are separate trust boundaries. The backend
persists hosts, jobs, custom tasks, its ED25519 identity and isolated
`known_hosts` data below `/data`.

### Semaphore legacy provider

Existing `0.1` config entries migrate to the optional Semaphore provider. New
Semaphore setups require the Semaphore URL/token/project, a separate status URL,
four template IDs, polling interval and TLS choice. See the
[migration guide](docs/04-operations/migration-0.1-to-0.2.md).

## Development

Python `3.14` and `uv` are required:

```bash
uv sync --locked
make browser-install
make quality
```

Tests mock all HTTP and execution boundaries. They never contact a real backend,
run Ansible against a host, install updates or reboot a host. Start with
[AGENTS.md](AGENTS.md) and the [Obsidian-ready documentation](docs/README.md).

The container publication model and anonymous GHCR verification are documented
in [Release and publication](docs/04-operations/release-and-publication.md).

## Removal

Delete the Home Assistant config entry, then remove the integration. Stop and
remove the app or container separately. Deleting its persistent volume also
deletes the database and SSH identity and is intentionally not part of normal
removal.

## License

MIT, see [LICENSE](LICENSE).
