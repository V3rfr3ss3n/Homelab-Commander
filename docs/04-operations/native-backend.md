---
title: Native Backend Betrieb
status: active
updated: 2026-08-21
tags: [operations, backend, docker, ssh, ansible]
---

# Native Backend Betrieb

## Betriebsarten

`Dockerfile` ist die gemeinsame Image-Quelle. `compose.yaml` startet dieses Image
standalone; `addon/homelab_updates/config.yaml` referenziert dasselbe Multi-Arch-
Image für Home Assistant. Persistente Daten liegen immer unter `/data`:

- `homelab_updates.db` – Hosts, Jobs, Logs und Custom Tasks
- `ssh/id_ed25519` – privater ED25519-Key mit Modus `0600`
- `ssh/known_hosts` – isolierte First-use-Hostkey-Datenbank

Die App benötigt weder Host-Netzwerk, Docker-Socket noch Home-Assistant-
Konfigurationszugriff. `/tmp` ist flüchtig. Backups müssen `/data` schützen.

### Standalone Quick Start

```bash
read -rsp 'Backend API token (at least 32 random characters): ' HUL_API_TOKEN
export HUL_API_TOKEN
docker compose config --quiet
docker compose up --build --detach
docker compose ps
```

Das Token gehört nicht in eine committete `.env`. `compose.yaml` veröffentlicht
Port 8099 standardmäßig nur auf `127.0.0.1`. Stoppen ohne Datenverlust erfolgt mit
`docker compose down`; das benannte Volume wird dabei nicht gelöscht.

## Konfiguration

| Variable/Option | Pflicht | Bedeutung |
| --- | --- | --- |
| `HUL_API_TOKEN` / `api_token` | ja | mindestens 32 zufällige Zeichen |
| `HUL_DATA_DIR` | Standalone optional | Standard `/data` |
| `HUL_LOG_LEVEL` / `log_level` | optional | `INFO` als Standard |
| `HUL_ALLOW_SHELL_TASKS` / `allow_shell_tasks` | optional | Standard `false` |

`HUL_INGRESS_MODE` ist keine Benutzeroption. Der Container setzt ihn nur, wenn
Supervisor-Optionen unter `/data/options.json` vorhanden sind.

## Remote-Host vorbereiten

1. Einen eigenen, nicht persönlich genutzten Automationsbenutzer anlegen.
2. Den im Ingress-UI oder `GET /api/v1/public-key` angezeigten Public Key in
   dessen `authorized_keys` eintragen.
3. SSH-Zugriff durch Firewall/Netzsegment auf den Backend-Host begrenzen.
4. Python und APT auf Debian/Ubuntu bereitstellen.
5. Für die eingebauten Update-/Reboot-Module non-interactive `sudo` erlauben.

Ansible führt Module als temporären Python-Code aus. Eine zuverlässige
pfadbasierte sudoers-Whitelist für einzelne Modulbefehle ist deshalb nicht
möglich. Wird etwa folgende generische Regel verwendet, ist der Backend-Key
effektiv eine Root-Identität und muss entsprechend geschützt werden:

```sudoers
automation ALL=(root) NOPASSWD: ALL
```

Der Benutzername ist nur ein generisches Beispiel. Wer diese breite Regel nicht
akzeptiert, sollte einen eigenen eingeschränkten Execution Adapter oder eine
gehärtete Privilege-Escalation-Lösung einsetzen; nicht einfach Secrets in Tasks
oder Home Assistant hinterlegen.

Der erste Kontakt verwendet OpenSSH `StrictHostKeyChecking=accept-new` und eine
eigene `known_hosts`-Datei. Das schützt spätere Verbindungen, verlangt aber eine
vertrauenswürdige Erstverbindung. Fingerprints sollten beim Onboarding außerhalb
dieses Repositorys geprüft werden.

## Job- und Fehlerbetrieb

- HTTP-Requests warten nicht auf Ansible; sie liefern einen Job zurück.
- Abgebrochene `running`-Jobs werden nach Backend-Neustart wieder eingereiht.
- Mutierende Jobs desselben Hosts laufen nie parallel.
- Logs enden bei 64 KiB und redigieren Zieladresse und Remote-Benutzer.
- Ein Update prüft danach den Status, löst aber keinen Reboot aus.
- Ein fehlender oder gelöschter Zielhost führt zu einem sicheren Fehlercode.

## Custom Tasks

`command` speichert ein JSON-Argumentarray und verwendet
`ansible.builtin.command`. Das verhindert Shell-Expansion. `shell` verwendet
ausdrücklich `ansible.builtin.shell`, muss zusätzlich auf Deployment-Ebene
freigeschaltet sein und sollte Ausnahme bleiben. Taskdefinitionen dürfen keine
Tokens, Passwörter oder private Schlüssel enthalten.

## Wiederherstellung und Entfernung

Ein Restore benötigt den vollständigen `/data`-Inhalt, besonders Datenbank,
Private Key und `known_hosts`. Wird nur die Datenbank wiederhergestellt, erkennen
Hosts den neuen Key nicht. Das Löschen des Volumes ist irreversibel und nicht Teil
eines normalen Integration-Uninstalls.
