// Keep /homelab-updates as the stable, administrator-only sidebar entry.
// Supervisor owns local Ingress authentication; remote backends own their login.
class HomelabUpdatesPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode: "open"});
    this._destination = null;
  }

  set panel(value) {
    this._panel = value;
    this._openBackend();
  }

  connectedCallback() {
    this._openBackend();
  }

  _openBackend() {
    const destination = this._panel?.config?.management_url;
    if (!this.isConnected || !destination || destination === this._destination) return;
    let url;
    try {
      url = new URL(destination, window.location.origin);
    } catch {
      return;
    }
    const localApp = destination.startsWith("/app/") && url.origin === window.location.origin;
    const remoteBackend = /^https?:\/\//.test(destination) && !url.username && !url.password;
    if (!localApp && !remoteBackend) return;
    this._destination = destination;

    // Replacement avoids sending Back through this redirect again.
    window.location.replace(url.href);
  }
}

if (!customElements.get("homelab-updates-panel")) {
  customElements.define("homelab-updates-panel", HomelabUpdatesPanel);
}
