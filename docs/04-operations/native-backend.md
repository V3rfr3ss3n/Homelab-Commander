---
title: Native Backend Betrieb
status: active
updated: 2026-08-22
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

Nach dem Start liegt die Management-UI am veröffentlichten Server-Root. Im
Standalone-Modus wird das API-Token beim Verbinden genau einmal gesendet und
danach aus dem Eingabefeld/JavaScript verworfen. Das Backend setzt stattdessen
eine opaque HttpOnly-Session mit acht Stunden absoluter und 60 Minuten Idle-
Lifetime. F5 stellt diese Session wieder her; Disconnect, Ablauf oder Backend-
Neustart verlangen das Token erneut. Das Session-Cookie ist bei erkanntem HTTPS
`Secure`. Ein TLS-Reverse-Proxy muss das ursprüngliche Scheme daher
vertrauenswürdig weiterreichen. Für Zugriff aus dem LAN muss das Port-Mapping
bewusst gebunden und durch Firewall beziehungsweise Reverse Proxy geschützt
werden; native TLS-Terminierung ist derzeit nicht enthalten.

Während Jobs aktiv sind, aktualisiert die UI Jobs und Hosts alle 1,5 Sekunden.
Ohne aktive Jobs stoppt schnelles Polling. Temporäre Fehler verwenden 3-/5-
Sekunden-Backoff; Disconnect und Page-Unload beenden den Poller sofort.

Ein Klick auf **Open** öffnet `#/jobs/<job-id>`. Die Route zeigt Jobmetadaten und
den redigierten Log, bleibt unter einem Ingress-Prefix relativ und enthält kein
Token. Ohne gültige Standalone-Session bleibt der Deep Link erhalten, zeigt aber
zunächst **Not connected**; nach dem Verbinden wird der gewünschte Job geladen.

### Home Assistant Hauptansicht

Mit einem geladenen Native-Config-Entry erscheint für Administratoren
**Homelab Updates** direkt in Home Assistants Seitenleiste. Diese Hauptansicht
zeigt Backendstatus, Hosts, laufende/wartende Jobs, den letzten Job und den
historisch letzten Fehler. **Hosts prüfen** startet echte Check-Jobs für alle
verwalteten Hosts. Die normalen Coordinator-Polls laufen automatisch und haben
deshalb keinen zusätzlichen Aktualisieren-Button.

**Log öffnen** lädt den redigierten Backendlog nur bei Bedarf über Home Assistants
authentifizierte Verbindung. **Backend verwalten** öffnet die konfigurierte
Backend-Basis-URL in einem neuen Tab. Diese URL muss aus dem Browser erreichbar
sein; eine interne App-URL ist dafür ungeeignet. Beim Home-Assistant-App-Betrieb
öffnet der separate Seitenleisteneintrag **Homelab Updates Backend** stattdessen
die Supervisor-Ingress-Verwaltung.

## Konfiguration

| Variable/Option | Pflicht | Bedeutung |
| --- | --- | --- |
| `HUL_API_TOKEN` / `api_token` | ja | mindestens 32 zufällige Zeichen |
| `HUL_DATA_DIR` | Standalone optional | Standard `/data` |
| `HUL_LOG_LEVEL` / `log_level` | optional | `INFO` als Standard |
| `HUL_ALLOW_SHELL_TASKS` / `allow_shell_tasks` | optional | Standard `false` |

`HUL_INGRESS_MODE` ist keine Benutzeroption. Der Container setzt ihn nur, wenn
Supervisor-Optionen unter `/data/options.json` vorhanden sind.

## Netzwerkweg zum verwalteten Host

Der native Provider kontaktiert Semaphore nicht. Ansible und OpenSSH bauen die
SSH-Verbindung direkt vom laufenden Backend-Prozess zum eingetragenen Host auf.
Bei einem Entwicklungsstart ist damit das Netzwerk des Entwicklungsrechners
maßgeblich; im Container ist es dessen Bridge-Netz. Der jeweilige Ursprung
benötigt eine ausgehende Route und Firewall-Freigabe zum konfigurierten SSH-Port.
Host-Netzwerk ist normalerweise nicht erforderlich. Eine eingehende Bind-Adresse
von Uvicorn steuert nur den Zugriff auf UI/API und schafft keine SSH-Route.

Ein Verbindungstest prüft genau diesen Weg. Fehler werden in der UI sichtbar
gemeldet; Entwicklung und CI verwenden ausschließlich synthetische Executor und
kontaktieren niemals einen echten Host.

## Remote-Host vorbereiten

1. Einen eigenen, nicht persönlich genutzten Automationsbenutzer anlegen.
2. Den im Ingress-UI oder `GET /api/v1/public-key` angezeigten Public Key in
   dessen `authorized_keys` eintragen.
3. SSH-Zugriff durch Firewall/Netzsegment auf den Backend-Host begrenzen.
4. Python 3 und APT auf Debian/Ubuntu bereitstellen. Ein unversionierter
   `/usr/bin/python`-Symlink ist nicht erforderlich.
5. Für die eingebauten Update-/Reboot-Module non-interactive `sudo` erlauben.

`Test connection` prüft nicht nur den SSH-Ping. Es sammelt mit derselben
`auto_silent`-Interpreterstrategie wie jeder spätere Lauf minimale Python-,
Distribution- und Kernel-Facts und führt anschließend ein harmloses
privilegiertes `true` aus. Ein erfolgreicher Test bestätigt damit auch, dass die
Voraussetzungen für die privilegierte APT-Phase grundsätzlich vorliegen. Der
erkannte Pfad wird bewusst nicht gespeichert: Ansible ermittelt ihn bei jedem
isolierten Lauf konsistent neu, sodass Paketupgrades oder geänderte Interpreter
keinen veralteten Hostzustand hinterlassen.

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
- Home Assistant speichert nur kompakte Jobmetadaten. Vollständige Logs bleiben
  im Backend und benötigen External-API-, Standalone-Session-, Ingress- oder
  administratorgeschützte Home-Assistant-Panel-Auth.
- Aktueller letzter Job und historisch letzter fehlgeschlagener Job sind getrennt;
  ein späterer Erfolg lässt einen älteren Fehler nur im historischen Sensor stehen.
- Ein Update prüft danach den Status, löst aber keinen Reboot aus.
- Ein fehlender oder gelöschter Zielhost führt zu einem sicheren Fehlercode.

### Ablauf von `check_updates`

1. Minimale Facts einschließlich Distribution, Version, Kernel und Python lesen.
2. APT-Metadaten mit `ansible.builtin.apt` und `become` aktualisieren.
3. `/usr/bin/apt list --upgradable` mit `LC_ALL=C` und `LANG=C` ohne Shell lesen.
4. `/var/run/reboot-required` mit `ansible.builtin.stat` prüfen.

`changed=false`, eine leere Paketliste, null Security Updates und eine fehlende
Rebootdatei sind normale erfolgreiche Zustände. Die bekannte Warnung der
`apt`-CLI bleibt im Joblog, beeinflusst aber den Taskstatus nicht. Paketzeilen
werden in einem begrenzten Debian-Provider-Parser ausgewertet; es gibt keinen
`grep`-Unterprozess und damit auch keinen Fehler bei null Treffern.

Ansible-Ausführung und Fachdaten sind getrennt: Ein privater stdout-Callback
schreibt genau ein markiertes JSON-Envelope. Das Backend verlangt gleichzeitig
Prozess-Exit `0`, Event `ok` und ein objektförmiges Resultat. Warnungen, stderr und
sonstige Diagnoseausgabe werden nur als technisches Joblog gespeichert.

### Fehlercodes

| Code | Bedeutung / erste Maßnahme |
| --- | --- |
| `python_interpreter_unavailable` | Python 3 fehlt oder wurde nicht ausführbar erkannt |
| `sudo_unavailable` | non-interactive sudo oder `sudo` selbst fehlt |
| `apt_lock_unavailable` | APT/dpkg wird gerade von einem anderen Prozess gehalten; später erneut prüfen |
| `check_updates_facts_failed` | Facts-/Distributionsphase fehlgeschlagen |
| `check_updates_apt_cache_refresh_failed` | privilegierter APT-Cache-Refresh fehlgeschlagen |
| `check_updates_package_list_failed` | locale-stabile Paketabfrage fehlgeschlagen |
| `check_updates_reboot_status_failed` | Reboot-Dateistatus konnte nicht gelesen werden |
| `invalid_ansible_output` | Exit war erfolgreich, aber das strukturierte Callback-Resultat fehlte oder war ungültig |

Die Management-UI übersetzt diese stabilen Kategorien in verständliche Texte.
Der authentifizierte Log-Dialog enthält die redigierten technischen Details. Bei
einem APT-Lock zuerst den konkurrierenden Paketprozess regulär beenden lassen;
Lockdateien nicht blind löschen.

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
