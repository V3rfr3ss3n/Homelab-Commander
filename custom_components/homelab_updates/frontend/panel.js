const TEXT = {
  de: {
    title: "Homelab Commander",
    subtitle: "Zentrale Übersicht für Hosts, Jobs und Backend-Zustand",
    online: "Online",
    offline: "Offline",
    check: "Hosts prüfen",
    checking: "Prüfung läuft…",
    management: "Backend verwalten",
    running: "Laufende Jobs",
    queued: "Wartende Jobs",
    hosts: "Hosts",
    lastJob: "Letzter Job",
    lastFailed: "Letzter fehlgeschlagener Job",
    recentJobs: "Letzte Jobs",
    noJobs: "Noch keine Jobs vorhanden.",
    noFailure: "Kein fehlgeschlagener Job vorhanden.",
    noHosts: "Noch keine Hosts vorhanden.",
    type: "Typ",
    state: "Status",
    host: "Host",
    finished: "Beendet",
    duration: "Dauer",
    error: "Fehler",
    updates: "Updates",
    security: "Sicherheit",
    reboot: "Neustart erforderlich",
    checked: "Zuletzt geprüft",
    log: "Log öffnen",
    close: "Schließen",
    logTitle: "Redigierter Joblog",
    logLoading: "Log wird geladen…",
    logFailed: "Der Joblog konnte nicht geladen werden.",
    checkStarted: "Hostprüfung wurde gestartet.",
    checkFailed: "Die Hostprüfung konnte nicht gestartet werden.",
    yes: "Ja",
    no: "Nein",
    unknown: "—",
    loading: "Ansicht wird geladen…",
  },
  en: {
    title: "Homelab Commander",
    subtitle: "Central overview for hosts, jobs, and backend health",
    online: "Online",
    offline: "Offline",
    check: "Check hosts",
    checking: "Check running…",
    management: "Manage backend",
    running: "Running jobs",
    queued: "Queued jobs",
    hosts: "Hosts",
    lastJob: "Last job",
    lastFailed: "Last failed job",
    recentJobs: "Recent jobs",
    noJobs: "No jobs yet.",
    noFailure: "No failed job yet.",
    noHosts: "No hosts yet.",
    type: "Type",
    state: "State",
    host: "Host",
    finished: "Finished",
    duration: "Duration",
    error: "Error",
    updates: "Updates",
    security: "Security",
    reboot: "Reboot required",
    checked: "Last checked",
    log: "Open log",
    close: "Close",
    logTitle: "Redacted job log",
    logLoading: "Loading log…",
    logFailed: "The job log could not be loaded.",
    checkStarted: "Host check started.",
    checkFailed: "The host check could not be started.",
    yes: "Yes",
    no: "No",
    unknown: "—",
    loading: "Loading view…",
  },
};

const STYLE = `
  :host{display:block;min-height:100%;background:var(--primary-background-color);color:var(--primary-text-color);font-family:var(--paper-font-body1_-_font-family,system-ui)}
  *{box-sizing:border-box}.page{max-width:1280px;margin:0 auto;padding:24px}.hero{display:flex;align-items:flex-start;justify-content:space-between;gap:24px;margin-bottom:24px}.hero h1{margin:0;font-size:28px}.subtitle{color:var(--secondary-text-color);margin-top:6px}.actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.status{padding:7px 12px;border-radius:999px;font-weight:700}.online{background:color-mix(in srgb,var(--success-color,#43a047) 20%,transparent);color:var(--success-color,#66bb6a)}.offline{background:color-mix(in srgb,var(--error-color,#db4437) 20%,transparent);color:var(--error-color,#ef5350)}button,.link{font:inherit;border:1px solid var(--divider-color);border-radius:9px;padding:9px 13px;background:var(--card-background-color);color:var(--primary-text-color);cursor:pointer;text-decoration:none}button.primary{border-color:var(--primary-color);background:var(--primary-color);color:var(--text-primary-color,#fff)}button:disabled{opacity:.55;cursor:wait}.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px;margin-bottom:18px}.card{background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:14px;padding:17px;box-shadow:var(--ha-card-box-shadow,none)}.label{color:var(--secondary-text-color);font-size:13px;margin-bottom:7px}.value{font-size:23px;font-weight:650}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:16px}.wide{grid-column:1/-1}.card h2{margin:0 0 14px;font-size:19px}.rows{display:grid}.row{display:grid;grid-template-columns:minmax(150px,1fr) auto;align-items:center;gap:14px;padding:11px 0;border-top:1px solid var(--divider-color)}.row:first-child{border-top:0}.row-main{min-width:0}.row-title{font-weight:600;overflow-wrap:anywhere}.meta{color:var(--secondary-text-color);font-size:13px;margin-top:4px;overflow-wrap:anywhere}.state-failed{color:var(--error-color,#ef5350)}.state-success{color:var(--success-color,#66bb6a)}.state-running,.state-queued{color:var(--warning-color,#ffa726)}.empty{color:var(--secondary-text-color);padding:8px 0}.notice{min-height:22px;margin:0 0 10px;color:var(--secondary-text-color)}.notice.error{color:var(--error-color,#ef5350)}.log-card{margin-bottom:18px}.log-head{display:flex;justify-content:space-between;align-items:center;gap:12px}.log-head h2{margin:0}.mono{margin:15px 0 0;padding:14px;border-radius:9px;background:var(--code-editor-background-color,#111827);color:var(--primary-text-color);white-space:pre-wrap;overflow-wrap:anywhere;max-height:55vh;overflow:auto;font-family:ui-monospace,SFMono-Regular,monospace;font-size:13px}@media(max-width:700px){.page{padding:16px}.hero{display:grid}.actions{width:100%}.grid{grid-template-columns:1fr}.row{grid-template-columns:1fr}.row button{justify-self:start}}
`;

function create(tag, options = {}, children = []) {
  const element = document.createElement(tag);
  if (options.className) element.className = options.className;
  if (options.text !== undefined) element.textContent = String(options.text);
  if (options.href) element.href = options.href;
  if (options.target) element.target = options.target;
  if (options.rel) element.rel = options.rel;
  for (const child of children) element.append(child);
  return element;
}

class HomelabUpdatesPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode: "open"});
    this._snapshot = null;
    this._unsubscribe = null;
    this._subscribing = false;
    this._log = null;
    this._notice = "";
    this._noticeError = false;
  }

  set hass(value) {
    this._hass = value;
    this._subscribe();
    this._render();
  }

  set panel(value) {
    this._panel = value;
    this._subscribe();
    this._render();
  }

  connectedCallback() {
    this._subscribe();
    this._render();
  }

  disconnectedCallback() {
    if (this._unsubscribe) this._unsubscribe();
    this._unsubscribe = null;
  }

  get _config() {
    return this._panel?.config || {};
  }

  get _text() {
    return TEXT[this._hass?.language?.startsWith("de") ? "de" : "en"];
  }

  async _subscribe() {
    if (!this.isConnected || !this._hass || !this._config.entry_id || this._unsubscribe || this._subscribing) return;
    this._subscribing = true;
    try {
      this._unsubscribe = await this._hass.connection.subscribeMessage(
        (snapshot) => {
          this._snapshot = snapshot;
          this._render();
        },
        {type: "homelab_updates/subscribe_panel", entry_id: this._config.entry_id},
      );
    } catch (error) {
      this._notice = error instanceof Error ? error.message : String(error);
      this._noticeError = true;
      this._render();
    } finally {
      this._subscribing = false;
    }
  }

  _date(value) {
    if (!value) return this._text.unknown;
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? this._text.unknown : new Intl.DateTimeFormat(this._hass?.language || "en", {dateStyle: "medium", timeStyle: "short"}).format(parsed);
  }

  _duration(value) {
    return typeof value === "number" ? `${value.toFixed(1)} s` : this._text.unknown;
  }

  _summary(label, value) {
    return create("section", {className: "card"}, [
      create("div", {className: "label", text: label}),
      create("div", {className: "value", text: value}),
    ]);
  }

  _jobSummary(job, emptyText) {
    if (!job) return create("div", {className: "empty", text: emptyText});
    return create("div", {className: "rows"}, [
      this._jobRow(job),
    ]);
  }

  _jobRow(job, withLog = true) {
    const title = `${job.type || this._text.unknown} · ${job.state || this._text.unknown}`;
    const details = [job.host_name, this._date(job.finished_at || job.created_at), job.error_code].filter(Boolean).join(" · ");
    const content = create("div", {className: "row-main"}, [
      create("div", {className: `row-title state-${job.state || "unknown"}`, text: title}),
      create("div", {className: "meta", text: details || job.job_id}),
    ]);
    const children = [content];
    if (withLog && job.log_available) {
      const button = create("button", {text: this._text.log});
      button.addEventListener("click", () => this._openLog(job));
      children.push(button);
    }
    return create("div", {className: "row"}, children);
  }

  _hostRow(host) {
    const system = host.distribution || host.status || this._text.unknown;
    const details = `${system} · ${this._text.updates}: ${host.updates} · ${this._text.security}: ${host.security_updates}`;
    return create("div", {className: "row"}, [
      create("div", {className: "row-main"}, [
        create("div", {className: "row-title", text: host.name}),
        create("div", {className: "meta", text: details}),
        create("div", {className: "meta", text: `${this._text.checked}: ${this._date(host.checked_at)} · ${this._text.reboot}: ${host.reboot_required ? this._text.yes : this._text.no}`}),
      ]),
    ]);
  }

  async _checkHosts(button) {
    button.disabled = true;
    try {
      await this._hass.callWS({type: "homelab_updates/check_hosts", entry_id: this._config.entry_id});
      this._notice = this._text.checkStarted;
      this._noticeError = false;
    } catch {
      this._notice = this._text.checkFailed;
      this._noticeError = true;
    }
    this._render();
  }

  async _openLog(job) {
    this._log = {job, output: this._text.logLoading, loading: true};
    this._render();
    try {
      const result = await this._hass.callWS({type: "homelab_updates/job_log", entry_id: this._config.entry_id, job_id: job.job_id});
      this._log = {job, output: `${result.output || ""}${result.truncated ? "\n[truncated]" : ""}`, loading: false};
    } catch {
      this._log = {job, output: this._text.logFailed, loading: false};
    }
    this._render();
  }

  _renderLog() {
    if (!this._log) return null;
    const close = create("button", {text: this._text.close});
    close.addEventListener("click", () => {
      this._log = null;
      this._render();
    });
    return create("section", {className: "card log-card"}, [
      create("div", {className: "log-head"}, [
        create("h2", {text: `${this._text.logTitle}: ${this._log.job.type}`}),
        close,
      ]),
      create("div", {className: "meta", text: this._log.job.job_id}),
      create("pre", {className: "mono", text: this._log.output}),
    ]);
  }

  _render() {
    if (!this.shadowRoot) return;
    const style = create("style", {text: STYLE});
    if (!this._snapshot) {
      this.shadowRoot.replaceChildren(style, create("main", {className: "page"}, [
        create("header", {className: "hero"}, [
          create("div", {}, [create("h1", {text: this._text.title}), create("div", {className: "subtitle", text: this._text.subtitle})]),
        ]),
        create("section", {className: "card empty", text: this._notice || this._text.loading}),
      ]));
      return;
    }
    const snapshot = this._snapshot;
    const status = create("span", {className: `status ${snapshot.backend_online ? "online" : "offline"}`, text: snapshot.backend_online ? this._text.online : this._text.offline});
    const check = create("button", {className: "primary", text: snapshot.checking ? this._text.checking : this._text.check});
    check.disabled = Boolean(snapshot.checking || !snapshot.backend_online);
    check.addEventListener("click", () => this._checkHosts(check));
    const actions = [status, check];
    if (this._config.management_url) {
      const localApp = this._config.management_url.startsWith("/app/");
      actions.push(create("a", {
        className: "link",
        text: this._text.management,
        href: this._config.management_url,
        target: localApp ? "" : "_blank",
        rel: localApp ? "" : "noopener noreferrer",
      }));
    }
    const pageChildren = [
      create("header", {className: "hero"}, [
        create("div", {}, [create("h1", {text: this._text.title}), create("div", {className: "subtitle", text: this._text.subtitle})]),
        create("div", {className: "actions"}, actions),
      ]),
      create("p", {className: `notice${this._noticeError ? " error" : ""}`, text: this._notice}),
    ];
    const log = this._renderLog();
    if (log) pageChildren.push(log);
    pageChildren.push(
      create("div", {className: "summary"}, [
        this._summary(this._text.hosts, snapshot.hosts.length),
        this._summary(this._text.running, snapshot.running_jobs),
        this._summary(this._text.queued, snapshot.queued_jobs),
      ]),
      create("div", {className: "grid"}, [
        create("section", {className: "card"}, [create("h2", {text: this._text.lastJob}), this._jobSummary(snapshot.last_job, this._text.noJobs)]),
        create("section", {className: "card"}, [create("h2", {text: this._text.lastFailed}), this._jobSummary(snapshot.last_failed_job, this._text.noFailure)]),
        create("section", {className: "card wide"}, [create("h2", {text: this._text.hosts}), snapshot.hosts.length ? create("div", {className: "rows"}, snapshot.hosts.map((host) => this._hostRow(host))) : create("div", {className: "empty", text: this._text.noHosts})]),
        create("section", {className: "card wide"}, [create("h2", {text: this._text.recentJobs}), snapshot.jobs.length ? create("div", {className: "rows"}, snapshot.jobs.map((job) => this._jobRow(job))) : create("div", {className: "empty", text: this._text.noJobs})]),
      ]),
    );
    this.shadowRoot.replaceChildren(style, create("main", {className: "page"}, pageChildren));
  }
}

if (!customElements.get("homelab-updates-panel")) {
  customElements.define("homelab-updates-panel", HomelabUpdatesPanel);
}
