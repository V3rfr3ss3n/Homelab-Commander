---
title: Configuration and authentication
status: active
updated: 2026-10-31
tags: [wiki, user-guide]
---

# Configuration and authentication

## Native integration

Use Home Assistant's config flow. Local App discovery is optional and validates
health before token/API validation. A stopped, missing or incompatible local App
does not remove the manual **Remote / standalone backend** option.

For a remote backend, enter a URL reachable **from Home Assistant**, for example
`https://backend.example.invalid`, and its API token. An Ingress browser URL is
not an external API URL. Existing remote entries are never silently rewritten by
discovery. Configuration, reauthentication and reconfiguration belong in HA's UI,
not source constants or YAML.

HTTPS and certificate verification are preferred. A per-entry verification option
does not disable SSL verification globally. Treat plain HTTP as a deliberate
trusted-network choice.

## Backend options

| Standalone variable | App option | Meaning |
| --- | --- | --- |
| `HUL_API_TOKEN` | `api_token` | Required random token, at least 32 characters |
| `HUL_DATA_DIR` | managed data directory | Persistent storage; standalone default `/data` |
| `HUL_LOG_LEVEL` | `log_level` | Logging level; default `INFO` |
| `HUL_ALLOW_SHELL_TASKS` | `allow_shell_tasks` | Explicit shell-task opt-in; default `false` |

Ingress mode is set by the App/container lifecycle, not a user option.

## Three authentication paths

- The external `/api/v1` API uses a Bearer token, including requests from HA.
- The standalone UI exchanges the entered token for a short-lived HttpOnly session.
  Reload validates that session; disconnect, expiry or backend restart require login.
- Ingress uses Supervisor authentication. The browser is not given the API token.

The standalone session lasts at most eight hours, with a 60-minute idle limit.
Its cookie is `SameSite=Strict`, restricted to `/ui-api`, and `Secure` under HTTPS.
A reverse proxy must forward the original scheme through a trusted setup. UI
mutations also require CSRF protection. Do not put credentials in links or browser
storage.

## Existing Semaphore installations

The optional Semaphore provider remains available for legacy installations.
Its status endpoint, command backend, project and action mappings are configured
through HA. Existing `0.1` entries migrate to that provider without changing entity
identities. The separate export/refresh action is a Semaphore-specific capability.
See [migration notes](../../04-operations/migration-0.1-to-0.2.md).
