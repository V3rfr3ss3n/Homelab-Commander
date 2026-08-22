# Homelab Updates app documentation

The app stores its SQLite database, managed ED25519 identity and isolated
`known_hosts` file under `/data`; Home Assistant includes these files in app
backups. The private key is never available through the API or Ingress UI.

The app does not request host networking, the Docker socket, Home Assistant
configuration mounts or privileged capabilities. Shell custom tasks are disabled
by default.

## Installation after publication

1. Open **Settings → Apps → App store** in Home Assistant.
2. Open the repository menu and add the final public repository URL.
3. Refresh the store and install **Homelab Updates**.
4. Set a random API token of at least 32 characters in **Configuration**.
5. Keep shell tasks disabled unless their remote-code risk is explicitly accepted.
6. Start the app, enable its **Homelab Updates Backend** sidebar entry and verify
   the Ingress dashboard.
7. Copy only the displayed public SSH key to the dedicated remote user.
8. Expose port `8099` only when the Home Assistant integration cannot reach the
   app through an internal route; the port remains protected by the same token.

The development repository intentionally does not name a final repository URL and
does not publish the referenced multi-architecture image yet. Consequently these
store steps are release instructions, not a claim that `0.2.0-dev.0` is currently
installable from a public app repository.
