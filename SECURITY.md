# Security Policy

## Reporting a vulnerability

Do not open a public issue for suspected vulnerabilities or accidental secret
exposure. Use the repository's
[private security advisory form](https://github.com/V3rfr3ss3n/Homelab-Commander/security/advisories/new).

Include the affected version, impact, reproduction steps using sanitized data,
and any suggested mitigation. Never include a working production token or an
unredacted Home Assistant diagnostic export.

## Supported versions

No version is supported yet because the integration has not been released. The
support policy will be defined before `0.1.0`.

## Security model

The integration is a controller for privileged automation. Its API token can
trigger operations on managed hosts, so users should grant the smallest practical
backend permissions, keep the backend on a trusted network, prefer HTTPS, and
rotate credentials if exposure is suspected.

See [security and privacy](docs/04-operations/security-and-privacy.md) for the
project's implementation requirements.
