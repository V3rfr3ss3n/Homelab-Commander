# Homelab Updates app

This Home Assistant app runs the same native backend image as the standalone
Docker deployment. Open its **Homelab Updates Backend** Ingress panel to manage
hosts and custom tasks; the integration's **Homelab Updates** panel remains the
operational Home Assistant overview.

Configure a random API token with at least 32 characters before first start.
The optional port is disabled by default; expose it only when the Home Assistant
integration cannot reach the app through an internal address.

The app pulls the public, versioned AMD64/AArch64 image without registry
credentials. Add
`https://github.com/V3rfr3ss3n/Homelab-Commander` to the App Store repositories.

See the
[full public operations guide](https://github.com/V3rfr3ss3n/Homelab-Commander/blob/main/docs/04-operations/native-backend.md).
