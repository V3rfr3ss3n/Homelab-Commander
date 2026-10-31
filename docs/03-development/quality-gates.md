---
title: Quality Gates
status: accepted
updated: 2026-10-31
tags: [development, quality, ci, testing]
---

# Quality Gates

Ein Merge oder Release ist nur bei vollständig grünem Gate erlaubt. `make quality`
ist die kanonische Schnittstelle für lokale Runs und CI. `make release-check`
ergänzt öffentliche URL-/Codeowner-Prüfungen.

## Lokal gezielt arbeiten, vollständig freigeben

- `make quality-fast` kombiniert die bestehenden Format-, Lint-, Typ-, Link- und
  Privacy-Prüfungen ohne Tests oder Dependency-Audit. Es ist eine Iterationshilfe,
  kein Merge-Gate.
- Verhalten gezielt prüfen: `uv run pytest tests/test_doc_links.py --no-cov`
  beziehungsweise den betroffenen Testpfad wählen. Diese Ergebnisse dürfen nicht
  als vollständige Coverage-Abnahme ausgegeben werden.
- Vor Merge bleibt `make quality` vollständig erforderlich. Keine automatische
  Pfadfilterung entfernt Tests, Audit oder die getrennten 95-%-Schwellen.
- `make release-check` enthält bereits `quality`; nicht beide nacheinander auf
  unverändertem Stand ausführen. Nach relevanten Änderungen erneut validieren.

GitLab verwendet `.gitlab-ci.yml` für denselben `make quality`-Aufruf mit
Lockfile, Chromium und synthetischen Tests. MR-Pipelines und `main` werden
geprüft; Feature-Pushes erzeugen keinen zusätzlichen zweiten Lauf. uv wird in einem
isolierten Verzeichnis aus dem offiziellen, SHA-256-geprüften Releasearchiv
installiert. Shell-Runner benötigen Python ab 3.12, Make, Git, OpenSSH und
Chromium-Systembibliotheken vorab; der Job installiert dort keine
Betriebssystempakete. Nur ein als Root laufender Wegwerf-Container installiert
diese Pakete selbst. GitHub behält
seine bestehenden Hassfest-, HACS-, Container- und Secret-Scan-Workflows. Diese
separaten Gates sind kein Bestandteil von `make quality` und müssen vor einer
Veröffentlichung ebenfalls bestätigt sein. Die GitLab-Konfiguration veröffentlicht
keine Images, ändert keine Rechte und konfiguriert keinen Mirror.

## Gate-Stufen

| Stufe | Werkzeug | Blockierendes Kriterium |
| --- | --- | --- |
| Format | Ruff | `ruff format --check .` ohne Diff |
| Lint | Ruff | `ruff check .` ohne ungeklärte Suppression |
| Types | Mypy | Strict Check ohne Fehler |
| Tests | Pytest + Playwright | alle Unit-/Integration-/Browsertests grün |
| Coverage | Coverage.py | mindestens 95 % Lines **und** 95 % Branches, unabhängig geprüft |
| HA validation | Hassfest | Manifest, Services, Übersetzungen und Struktur gültig |
| HACS | HACS Action | Repository als Integration valide |
| Container | HA Builder + Runtime-Skript | AMD64/AArch64 bauen; bei Publication anonymes Manifest/Pull und Laufzeitvertrag grün |
| Supply chain | Audit-Tool | keine ungeklärte bekannte Schwachstelle oder unzulässige Lizenz |
| Secrets | Gitleaks-artiger Scan | keine Secrets in Arbeitsbaum oder Git-Historie |
| Privacy | Projektpattern | keine reale Infrastruktur oder persönlichen Daten |
| Docs | `make docs` | lokale Dateiziele in Markdown und Obsidian vorhanden; öffentliche Anleitung aktuell |

`make docs` prüft ohne Netzwerkzugriff relative Markdown-Links, Bilder,
Referenzdefinitionen und relative Obsidian-Wikilinks. Es berücksichtigt getrackte
und neue, nicht ignorierte Dateien; ignorierte lokale Dateien gelten nicht als
veröffentlichbare Linkziele. Codebeispiele in Backticks oder Fences werden
übersprungen. Bei Wikilinks wird eine fehlende `.md`-Endung ergänzt, auch bei
Versionsnummern im Dateinamen. Externe URLs, Überschriftenanker, unaufgelöste
Referenzverwendungen und Obsidian-Vault-Suche nach bloßen Dateinamen werden nicht
validiert. Dokumentlinks verwenden deshalb explizite relative Pfade.

## Testpyramide

1. **Unit:** Parser, Modelle, Zustandsautomat, Redaction und Pure Functions.
2. **Adapter contracts:** gemockte HTTP-Requests/Responses und Fehlerabbildung.
3. **Home Assistant integration:** Config Flow, Coordinator, Registry, Entities,
   Lifecycle, Reauth/Reconfigure und Diagnostics.
4. **Browser:** echtes Headless Chromium gegen einen lokalen ASGI-Server im
   Standalone- und Ingress-Prefix-Modus sowie gegen einen synthetischen
   Home-Assistant-Panel-Harness; Execution Adapter bleibt synthetisch.
5. **Isolierte manuelle Abnahme:** temporäre Home-Assistant-Testinstanz und Fake-
   Backend; niemals ein produktives Homelab.

## Mindest-Testmatrix

- gültige, leere, teilweise und ungültige Statuspayloads
- Integer-/Boolean-/Timestamp-Grenzfälle sowie unbekannte Zusatzfelder
- Timeout, DNS/Connect, TLS, 401/403, 404, 429 und 5xx
- Duplicate Config, Reauth, Reconfigure, Reload und Unload
- neuer, verschwundener und umbenannter Host
- Updates 0, 1 und mehrstellig; Security Updates unabhängig davon
- Task waiting/running/success/failed/error/unknown/timeout/cancel
- Backendausfälle unabhängig voneinander
- Token nicht in Logs, Exceptions, Diagnostics oder Entityattributen
- Native Adapter: Exit-Code, `ok`/`failed`-Event und Warntext unabhängig prüfen
- Debian/Ubuntu: automatische Python-3-Erkennung ohne `python`-Symlink,
  sudo-/APT-Lock-Fehler, APT 0/normal/security und Rebootdatei vorhanden/fehlend
- Private Callback-Ausgabe mindestens synthetisch gegen localhost prüfen; niemals
  einen realen Host, Paketupdate oder Reboot aus dem Quality Gate starten
- Standalone UI: Login-Cookieflags, Token-Leakage, F5-Recovery, Ablauf,
  ungültige Session, Logout und CSRF; External Bearer und Ingress bleiben getrennt
- App Ingress: Standard-Root wird als `/` weitergereicht, nie als `//`; Root,
  Assets, UI-API, Deep Links und CSRF bleiben unter verschachteltem Prefix und
  lehnen direkte Nicht-Supervisor-Quellen ab
- Live UI: `queued → running → success/failed`, Hostrefresh, genau ein Poller,
  Stopp ohne aktive Jobs/bei Disconnect und Wiederaufnahme nach Reload
- HA sidebar: direkte Same-Tab-Navigation zur lokalen App beziehungsweise Remote-
  UI, Zurück ohne Redirectschleife, keine implizite Aktion oder Tokenweitergabe;
  bestehende admin-only WebSocket-Commands und token-/logfreier Statusstream
- Container: AMD64/AArch64, versionierte Labels, Port/Volume/Healthcheck,
  Ansible/OpenSSH und PID 1 nach Privilege Drop als UID `10001`

## Dependency Policy

- Runtime- und CI-Dependencies sind exakt oder reproduzierbar gepinnt.
- Dependabot oder Renovate erstellt Updates; CI entscheidet über Kompatibilität.
- Ein Auditfund wird bewertet und dokumentiert. Ein Ignore braucht Ablaufdatum,
  Begründung und Referenz.
- Release Actions werden auf unveränderliche Commit-SHAs gepinnt, soweit praktikabel.

### Native Backend Runtime

- `FastAPI` definiert die typisierte REST-Grenze und OpenAPI-Dokumentation.
- `Uvicorn` ist der schlanke ASGI-Prozess für Add-on und Standalone-Container.
- `ansible-core` stellt die agentenlose SSH-Ausführung und die geprüften
  Built-in-Module bereit; die Anwendung startet ausschließlich Argumentlisten.
- OpenSSH erzeugt und liest den persistenten ED25519-Schlüssel über feste
  Argumentlisten; dadurch ist keine zusätzliche Kryptografie-Runtime nötig.

`ansible-core` zieht transitiv `cryptography` ein. Der gemeinsame Lock verwendet
`50.0.1` für Entwicklung und Produktion; der Container führt keine nachträgliche
Installation außerhalb des Locks aus. Der HA-Teststack ist auf `2026.10.4` und
seine Frontend-/Testplugin-Versionen aktualisiert. Der Entwicklungsgraph ersetzt
HA's verwundbaren Pillow-Pin durch `13.0.0`; Pillow ist im Produktionsgraph nicht
enthalten. Begründung, Kompatibilitätsprüfung und Rückbaukriterium stehen in
[ADR-0010](../02-architecture/adr/0010-secure-test-dependency-replacements.md).
`make audit` verwendet keine Advisory-Ignores; SE-2026-001 ist behoben.

SQLite, Queue-Steuerung und Prozessausführung nutzen die Python-Standardbibliothek.
Dadurch entsteht für Persistenz und Worker keine zusätzliche Runtime-Abhängigkeit.

`httpx2` ist ausschließlich eine gepinnte Entwicklungsabhängigkeit. Starlettes
aktueller `TestClient` nutzt sie für isolierte ASGI-Requests; sie wird nicht in das
Backend-Container-Image oder die Home-Assistant-Integration aufgenommen.

`playwright` ist ebenfalls ausschließlich eine gepinnte Entwicklungsabhängigkeit.
Es prüft die ausgelieferte Management-UI mit echtem Chromium und einem lokalen,
synthetischen Backend. Ein neuer Entwicklungsrechner installiert den Browser
einmalig mit `make browser-install`; CI installiert Chromium samt Systempaketen
vor `make quality`.

`home-assistant-frontend` ist ausschließlich eine versionsgleich zu Home
Assistant gepinnte Entwicklungsabhängigkeit. Die isolierte HA-Testumgebung lädt
damit den echten `frontend`-/`panel_custom`-Lifecycle. In einer regulären Home-
Assistant-Installation gehört dieses Paket bereits zur Plattform und wird nicht
von der Custom Integration ausgeliefert oder nachinstalliert.

## Ausnahmen

Eine Ausnahme ist nur über eine dokumentierte, zeitlich begrenzte Entscheidung mit
Owner, Risiko, Kompensation und Ablaufdatum zulässig. Coverage wird nicht durch
`# pragma: no cover` erhöht, außer nach begründeter Review einer technisch nicht
erreichbaren Zeile.

Ruff-Suppressionen verwenden ausgeschriebene Rule-Namen. Die Preview-Regel
`non-empty-init-module` ist ausschließlich für
`custom_components/homelab_updates/__init__.py` ausgenommen, weil Home Assistant
dort die Lifecycle-Hooks und `CONFIG_SCHEMA` lädt. Alle übrigen neuen Preview-
Regeln bleiben aktiv.

## Referenzziel

Das Projekt orientiert sich an Home Assistants Integration Quality Scale: Gold als
Nutzerqualitätsbaseline, ergänzt um strikte Typisierung und vollständig asynchrone
Abhängigkeiten. Nicht anwendbare Core-Regeln werden im späteren
`quality_scale.yaml` ausdrücklich begründet.
