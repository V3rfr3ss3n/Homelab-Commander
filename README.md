# Homelab Updates

Homelab Updates is a local-polling Home Assistant custom integration that shows
Linux package status as native Home Assistant devices and runs explicit
maintenance actions through Semaphore and Ansible.

> [!NOTE]
> Version `0.1.0` is implemented but has not been publicly released. The public
> repository URLs must be configured before creating a release.

## Features

- Setup, reauthentication, and reconfiguration entirely in Home Assistant's UI
- Any number of hosts discovered dynamically from one JSON status endpoint
- One Home Assistant device per stable inventory host ID
- Native update entity with install support and asynchronous progress tracking
- Available update, security update, kernel, distribution, and last-check sensors
- Reboot-required binary sensor and explicit host reboot button
- Local light/dark-compatible branding for Home Assistant 2026.3 and newer
- Native repair notification with confirmation before a required reboot
- Global check-all and status-export/refresh buttons
- Central polling: exactly one status request per coordinator refresh
- Independent status and command failure domains
- English and German UI translations
- Privacy-preserving diagnostics without host identities or credentials
- HACS-compatible layout and comprehensive automated quality gates

## Architecture

```text
Home Assistant UI and entities
             |
       application services
        /               \
status provider     automation backend
        |                  |
 local status API     Semaphore + Ansible
                           |
                       Linux hosts
```

Entity modules do not know Semaphore endpoint details. External payloads are
parsed into immutable domain models at adapter boundaries, making a future
dedicated operations backend possible without rewriting entity platforms.

## Requirements

- Home Assistant `2026.8.0` or newer
- Semaphore with a project accessible through its HTTP API
- Four task templates:
  - check all managed hosts
  - update one host with the Semaphore Limit Prompt enabled
  - reboot one host with the Limit Prompt enabled
  - export or refresh the status document
- An HTTP or HTTPS endpoint serving the expected status JSON

Home Assistant never connects to hosts using SSH and does not run Ansible itself.

## Installation

### Manual development installation

1. Copy `custom_components/homelab_updates` into the Home Assistant configuration
   directory under `custom_components/`.
2. Restart Home Assistant.
3. Clear the browser cache if the integration does not appear immediately.
4. Continue with [Setup](#setup).

### HACS

HACS installation will be documented after the first public GitHub release. Until
then, do not treat development snapshots as supported releases.

## Semaphore setup

Create four templates in one project and record their numeric IDs. Host-specific
update and reboot templates must allow Semaphore's Limit Prompt, because the
integration supplies the stable inventory host ID as `limit`.

Conceptually, actions are sent as:

```json
{
  "template_id": 12,
  "limit": "node-01"
}
```

The IDs are examples only. Every ID is entered in Home Assistant's UI and no
project-specific value is compiled into the integration.

Use a dedicated API token with the smallest permissions that can read the project
and start or inspect the required tasks.

## Expected status JSON

The endpoint returns one JSON object. Each top-level key is the canonical and
stable Ansible inventory host ID:

```json
{
  "node-01": {
    "checked_at": "2026-01-15T12:00:00Z",
    "distribution": "Example Linux",
    "distribution_version": "1.0",
    "host": "node-01",
    "hostname": "example-node",
    "kernel": "1.0.0-generic",
    "reboot_required": false,
    "security_updates": 2,
    "status": "critical",
    "updates": 5
  }
}
```

`updates`, `security_updates`, `reboot_required`, and timezone-aware `checked_at`
are required. Descriptive text fields are optional. Unknown fields are ignored.
If the optional `host` field is present, it must equal its top-level key.

## Setup

1. Open **Settings → Devices & services → Add integration**.
2. Search for **Homelab Updates**.
3. Enter:
   - Semaphore base URL
   - API token
   - project ID
   - status document URL
   - the four template IDs
   - polling interval
   - whether TLS certificates must be verified
4. Submit the form. Home Assistant validates the backend project and the complete
   status payload before storing the entry.

HTTP is supported for isolated local networks. HTTPS with certificate validation
is the safe default. Configured URLs cannot contain credentials, fragments, or
query parameters.

Use **Reconfigure** on the integration entry to change endpoints, project,
templates, TLS behavior, or polling interval. An authentication failure starts a
dedicated reauthentication flow for replacing the token.

## Entities

Each discovered host receives:

| Platform | Entity | Purpose |
| --- | --- | --- |
| Update | System updates | Native install action; available when `updates > 0` |
| Sensor | Available updates | Total package count |
| Sensor | Security updates | Security package count |
| Sensor | Kernel | Diagnostic kernel string |
| Sensor | Distribution | Diagnostic OS name and version |
| Sensor | Last check | Timezone-aware timestamp |
| Binary sensor | Reboot required | Status-provided reboot flag |
| Button | Reboot | Host-limited restart; enabled only while a reboot is required |

The integration hub device contains **Check all hosts** and **Refresh status**
buttons. It never triggers automatic updates or reboots internally.

The restart action uses Home Assistant's native `restart` button class and an
alert icon. Home Assistant controls the final icon color according to the active
frontend theme; integrations cannot force a portable red entity color. The
button remains unavailable until the latest status explicitly reports
`reboot_required: true` and is also locked while an update or reboot is running.

## Data updates and task behavior

The coordinator fetches the entire host snapshot at the configured interval. All
entities read this in-memory snapshot and perform no network I/O in properties.

After a command starts, its Semaphore task is polled asynchronously with a bounded
deadline. A successful update, check, or status-export task requests a coordinator
refresh. Semaphore success alone never claims a host is updated: only the next
status payload changes update availability.

When the refreshed status reports that a reboot is required, Home Assistant
creates a warning under **Settings → System → Repairs**. Opening **Fix issue**
shows a confirmation that names the affected host and warns about service
interruption. Only submitting that dialog starts the host-limited reboot;
closing it postpones the action. No update ever reboots a host automatically.

If the status endpoint fails, status-driven entities become unavailable and
recover on a later successful poll. A command-backend failure does not discard the
last valid status snapshot. Missing hosts remain registered and become unavailable;
new hosts are added dynamically.

## Security and privacy

- Tokens are stored only in Home Assistant's config entry storage.
- Tokens, authorization headers, raw response bodies, and configuration dumps are
  never logged.
- Diagnostics redact the token, sanitize URLs, omit host IDs, and expose only
  aggregate runtime health.
- Redirects are disabled, response sizes and request durations are bounded, and
  TLS verification is disabled only for the selected config entry when explicitly
  configured.
- This repository uses only synthetic endpoints and host data.

See [SECURITY.md](SECURITY.md) and the detailed
[security model](docs/04-operations/security-and-privacy.md).

## Troubleshooting

### Integration icon still shows a placeholder

Homelab Updates includes local `brand/icon.png` and `brand/icon@2x.png` assets.
After replacing the integration files, restart Home Assistant and perform a hard
browser refresh. Home Assistant and browsers may retain the previous placeholder
in their brand cache for a while.

### Cannot connect

Verify that Home Assistant can resolve and reach both configured URLs. Confirm the
scheme, port, firewall rules, and TLS certificate. Redirecting endpoints are not
accepted.

### Invalid authentication

Create or rotate the Semaphore API token, then use the integration's reauthenticate
flow. Do not paste tokens into issues or logs.

### Invalid project

Confirm that the numeric project exists and the token can access it.

### Invalid status data

Validate that the endpoint returns a JSON object, not an HTML login/error page.
Check required scalar types and ensure `checked_at` contains a timezone.

### Task starts but affects no host

Enable the Limit Prompt on the Semaphore update/reboot template and confirm that
the JSON top-level host ID exactly matches the Ansible inventory name.

### Host is unavailable

Confirm the host is still present in the newest status document. Hosts are not
deleted merely because one snapshot omits them.

## Removal

1. Open **Settings → Devices & services → Homelab Updates**.
2. Delete the config entry.
3. Remove the integration from HACS or delete its custom component directory.
4. Restart Home Assistant after manual file removal.

Removing the integration does not modify Semaphore, Ansible, or managed hosts.

## Development

The project uses Python 3.14, uv, Ruff, Mypy strict, Pytest, Coverage, Hassfest,
HACS validation, dependency auditing, CodeQL, and secret/privacy scanning.

```bash
uv sync --locked
make quality
```

The test suite uses synthetic fixtures and intercepts every network request. It
must never contact a real backend. Read [CONTRIBUTING.md](CONTRIBUTING.md),
[AGENTS.md](AGENTS.md), and the [documentation vault](docs/README.md) before
changing behavior.

## Known limitations

- `0.1.0` supports one status provider and one Semaphore project per config entry.
- Individual package selection, automatic reboot, direct SSH, Windows updates,
  container updates, backup, snapshot, and VM lifecycle operations are out of
  scope.
- Removed hosts are retained as unavailable registry entries in `0.1.0`.
- A public HACS release is blocked until real repository URLs are configured in
  the manifest.

## License

MIT, see [LICENSE](LICENSE).
