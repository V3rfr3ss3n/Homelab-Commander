# Changelog

## 0.2.0-dev.1

- Updated the App Store icon and logo to the refreshed Homelab Commander brand.
- Fixed the default Ingress entry so the Supervisor forwards `/` instead of `//`.
- Restricted Ingress management routes to the Supervisor proxy while keeping the
  external API Bearer-authenticated.
- Replaced installed-App filesystem links with public GitHub documentation.

## 0.2.0-dev.0

- Initial public development build of the native Homelab Updates backend.
- Home Assistant Ingress management UI for hosts, jobs and custom tasks.
- Persistent ED25519 identity, SQLite state and bounded redacted job logs.
- Debian and Ubuntu update checks through the built-in Ansible execution adapter.
