# Homelab Updates app

This Home Assistant app runs the same native backend image as the standalone
Docker deployment. Open its Ingress panel to manage hosts and custom tasks.

Configure a random API token with at least 32 characters before first start.
The optional port is disabled by default; expose it only when the Home Assistant
integration cannot reach the app through an internal address.

See [the full operations guide](../../docs/04-operations/native-backend.md).
