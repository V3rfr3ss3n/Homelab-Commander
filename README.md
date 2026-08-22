# Homelab Updates

Homelab Updates is a public-safe Home Assistant project for viewing and
deliberately operating Linux update state. Version `0.2.0-dev.0` consists of:

- a Home Assistant custom integration;
- a native FastAPI/SQLite/Ansible backend;
- a Home Assistant app (formerly add-on) with an Ingress management page.

The backend also runs as the same standalone Docker image. Semaphore plus a
separate status endpoint remains available as an optional legacy provider.

> [!WARNING]
> `0.2.0-dev.0` is a development version, not a stable release. Repository and
> container publication are intentionally blocked until final public URLs and
> release verification are complete.

## What it provides

- UI-only provider selection, setup, reauthentication and reconfiguration
- stable UUID devices for native hosts; stable inventory IDs for Semaphore
- update, security-update, kernel, distribution and last-check sensors
- native update entities and explicit reboot buttons
- a reboot confirmation through Home Assistant Repairs when a reboot is needed
- persistent asynchronous jobs with queued/running/success/failed/cancelled states
- connectivity, queue counts, latest job and separate historical-failure entities
- an admin-only Home Assistant sidebar overview with on-demand redacted job logs
- dynamically discovered custom-task buttons
- backend-managed persistent ED25519 identity; the API exposes only its public key
- host and custom-task CRUD in an Ingress-compatible management page
- English and German Home Assistant and app configuration text
- strict typing, high line/branch coverage, dependency audit and privacy gates

Updates never trigger a reboot. Reboot remains a separate user action and is only
enabled when the newest host status explicitly reports that it is required.

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
 Add-on Ingress UI or standalone Docker
```

Home Assistant never receives private SSH material and never starts Ansible. Host
credentials, inventory, processes and persistent jobs stay inside the backend.
Entity modules know neither REST endpoint paths nor Semaphore payloads.

## Native backend: Docker Compose

1. Generate a random token of at least 32 characters outside this repository.
2. Export it as `HUL_API_TOKEN` in your shell or an uncommitted `.env` file.
3. Start the service:

   ```bash
   docker compose up --build -d
   ```

The sample binds the API only to `127.0.0.1:8099`. Change the port mapping only
when another machine must connect, and retain token authentication and network
filtering. Persistent state uses the `homelab-updates-data` volume.
The management UI is served at the same origin. Standalone exchanges the API
token once for an opaque, short-lived HttpOnly cookie; the token is not persisted
in browser storage or cookies. A normal reload recovers that session and reloads
the dashboard. Disconnect, expiry, or a backend restart returns to **Not
connected**. Active jobs update automatically without a manual Refresh click.
Each recent job opens at the token-free `#/jobs/<job-id>` route with compact
metadata and its bounded redacted log. The same deep link works below an Ingress
prefix and returns to the requested job after standalone authentication.

## Home Assistant app

The repository contains `repository.yaml` and the app under
`addon/homelab_updates`. Configure a random API token before first start, then use
the Ingress panel to copy the public SSH key, register hosts and create tasks.

The app requests no host network, Docker socket, Home Assistant configuration
mount or privileged capability. Its optional API port is disabled by default and
can be exposed from the app's Network settings when required by the integration.

## Home Assistant integration

Copy `custom_components/homelab_updates` to Home Assistant, restart Home
Assistant, then open **Settings → Devices & services → Add integration** and
choose one provider:

### Native backend

Enter the backend base URL, the same API token, poll interval and TLS choice. The
integration validates API v1 before storing the entry. A newly registered native
host is visible immediately, even before its first status check.

### Semaphore legacy provider

Enter the Semaphore URL/token/project, separate status URL, four template IDs,
poll interval and TLS choice. Host update and reboot templates must accept the
integration-supplied inventory limit.

Existing `0.1` config entries migrate automatically to the Semaphore provider.
See the [migration guide](docs/04-operations/migration-0.1-to-0.2.md).

The native hub exposes backend connectivity, running and queued job counts, the
latest job and type, and a separate latest failed job. Every host has the same
latest/latest-failed distinction. Entity attributes contain only compact
metadata and a token-free job URL; full output is never written to Home
Assistant state or Recorder.

For Native, administrators also get a **Homelab Updates** sidebar entry as the
main Home Assistant view. It shows hosts, current job counts, the latest job and
the separate latest failure. **Check hosts** is the single global manual action;
normal coordinator refreshes happen automatically. **Open log** retrieves one
bounded redacted log on demand through Home Assistant authentication, without
exposing the backend token to the browser. **Manage backend** opens the configured
browser-reachable backend URL. App installations retain a separate **Homelab
Updates Backend** Ingress entry for host and task administration.

## Managed host setup

The backend supports Debian and Ubuntu through `DebianAptProvider`. Register a
dedicated, least-privilege remote user, install the public key shown by the UI,
and grant only the sudo operations required by the APT and reboot Ansible modules.
Do not copy a private key into Home Assistant or the repository.

`Test connection` validates SSH, automatic Python 3 discovery, distribution facts
and non-interactive sudo using the same inventory policy as later jobs. A check
then refreshes APT metadata, reads a locale-stable update list and reports reboot
need; warnings remain in the technical job log and are not treated as failures.

Detailed commands and threat-model notes are in the
[native backend operations guide](docs/04-operations/native-backend.md).

## Custom tasks

Command tasks are stored as an argument array and run through
`ansible.builtin.command`, without shell interpretation. Shell tasks are a
separate visible mode and are disabled by default at deployment level. Never put
passwords or tokens in task commands; task definitions are returned to authorized
administrators for editing.

## Security and privacy

- API access uses a constant-time checked Bearer token.
- Standalone UI uses an eight-hour absolute/one-hour idle opaque HttpOnly session;
  the API token is sent only to the login endpoint.
- Ingress relies on Supervisor access control; mutations also require a per-process
  CSRF token.
- private SSH keys, authorization headers and configuration dictionaries are not
  returned or logged;
- job output is bounded, NUL-stripped and redacts the selected host address/user;
- job logs remain behind API-token, standalone-session or Ingress authentication
  and are never copied into Home Assistant entities or diagnostics;
- mutating jobs are serialized per host and unknown targets fail before execution;
- examples use only `example.invalid`, synthetic UUIDs and generic host names.

Read the complete [security model](docs/04-operations/security-and-privacy.md) and
[API contract](docs/02-architecture/native-api.md).

## Development

Python `3.14` and `uv` are required:

```bash
uv sync --locked
make browser-install
make quality
```

Tests mock every HTTP request and execution adapter. They never contact a real
backend, run Ansible against a host, update a host or reboot one. Start with
[AGENTS.md](AGENTS.md) and the [Obsidian-ready docs vault](docs/README.md).

## Removal

Delete the Home Assistant config entry, then remove the integration. Stop and
remove the app/container separately. Deleting the persistent backend volume also
deletes its database and SSH identity and is intentionally not part of normal
removal.

## License

MIT, see [LICENSE](LICENSE).
