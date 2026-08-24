# Homelab Commander Backend App

This App provides the native FastAPI backend, SQLite persistence, Ansible/OpenSSH
execution, persistent jobs, managed ED25519 identity and the **Homelab Commander
Backend** Ingress UI. The separate HACS integration provides Home Assistant
entities and the **Homelab Commander** operational panel.

## Installation

1. Install **Homelab Commander** from HACS and restart Home Assistant.
2. Add `https://github.com/V3rfr3ss3n/Homelab-Commander` in **Apps → App store
   → Repositories**.
3. Install **Homelab Commander Backend**, configure a random API token of at
   least 32 characters, and start it.
4. Open the Ingress page to add hosts and copy the public SSH key to the
   dedicated remote user.
5. Add the **Homelab Commander** integration and select the detected local App.
   Enter the same API token; Home Assistant OS and Supervised discover the
   internal App route automatically.

For Home Assistant Container/Core, a standalone backend, or a remote backend,
select **Remote / standalone backend** and provide a reachable URL. Do not use a
Supervisor Ingress URL as a backend API URL.

The App stores state below `/data` and never exposes its private key. It does
not request host networking, Docker access, Home Assistant configuration mounts
or privileged capabilities. Shell custom tasks stay disabled by default.

See the [full operations guide](https://github.com/V3rfr3ss3n/Homelab-Commander/blob/main/docs/04-operations/native-backend.md).
