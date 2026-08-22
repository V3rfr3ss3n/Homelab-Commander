---
title: Produktanforderungen
status: accepted
updated: 2026-08-22
tags: [product, requirements]
---

# Produktanforderungen

`MUST`, `SHOULD` und `MAY` sind verbindlich im Sinn von RFC 2119 zu lesen.

## Konfiguration

- **REQ-CFG-001 MUST:** Die Integration wird vollständig über Config Entries und
  Home Assistants UI eingerichtet; es gibt keine YAML-Konfiguration.
- **REQ-CFG-002 MUST:** URL des Status-Providers, Command-Backend-URL,
  Zugangsdaten, Backend-Projekt und Aktionszuordnungen sind konfigurierbar.
- **REQ-CFG-003 MUST:** Verbindungs-, Authentifizierungs-, Projekt- und
  Payloadfehler werden vor dem Anlegen des Eintrags differenziert gemeldet.
- **REQ-CFG-004 MUST:** Derselbe Backend-/Projektkontext kann nicht versehentlich
  doppelt eingerichtet werden.
- **REQ-CFG-005 MUST:** Reauthentication und Reconfigure sind in der UI möglich.
- **REQ-CFG-006 MUST:** HTTP ist für lokale Netze erlaubt; HTTPS und selektive
  SSL-Verifikation werden unterstützt. Es gibt keine globale SSL-Abschaltung.

## Hoststatus und Geräte

- **REQ-STA-001 MUST:** Ein Poll lädt alle Hosts in genau einem Statusrequest.
- **REQ-STA-002 MUST:** Host-IDs werden ausschließlich aus dem Payload erkannt;
  es existiert keine statische Hostliste.
- **REQ-STA-003 MUST:** Jeder Host besitzt ein stabiles Device-Identifier-Paar aus
  Domain und technischer Host-ID. Anzeigenamen dürfen sich ändern.
- **REQ-STA-004 MUST:** Neue Hosts erscheinen ohne Reload. Vorübergehend fehlende
  Hosts werden unavailable und nicht sofort aus der Registry gelöscht.
- **REQ-STA-005 MUST:** Unbekannte Felder werden ignoriert; fehlende optionale
  Felder zerstören nicht den gesamten Poll.
- **REQ-STA-006 MUST:** Updatezahlen, Rebootstatus und ISO-8601-Zeitpunkte werden
  strikt und nachvollziehbar normalisiert. Ungültige Pflichtwerte ergeben einen
  sicheren Payloadfehler.

## Entities

- **REQ-ENT-001 MUST:** Je Host existieren native Entities für System Update,
  verfügbare Updates, Security Updates, Kernel, Distribution, letzten Check,
  Rebootbedarf und expliziten Reboot.
- **REQ-ENT-002 MUST:** Updateverfügbarkeit wird ausschließlich durch
  `updates > 0` bestimmt.
- **REQ-ENT-003 MUST:** Letzter Check ist ein timezone-aware `datetime` mit
  Timestamp Device Class, kein Stringzustand.
- **REQ-ENT-004 MUST:** Entity-Namen und User-facing Fehler sind übersetzbar;
  mindestens Englisch und Deutsch werden ausgeliefert.
- **REQ-ENT-005 SHOULD:** Weniger zentrale Diagnoseentities werden passend
  kategorisiert oder standardmäßig deaktiviert.

## Commands und Tasks

- **REQ-CMD-001 MUST:** Check-all, Status-Export/Refresh, Host-Update und Host-
  Reboot werden durch eine backendunabhängige Anwendungsschnittstelle ausgelöst.
- **REQ-CMD-002 MUST:** Hostaktionen senden exakt die technische Host-ID als
  Zielbegrenzung.
- **REQ-CMD-003 MUST:** Taskzustände werden asynchron, begrenzt und cancelbar
  verfolgt. Unbekannte Zustände verursachen keinen Crash.
- **REQ-CMD-004 MUST:** Ein erfolgreicher Task stößt einen Statusrefresh an; erst
  dessen Daten entscheiden über den sichtbaren Endzustand.
- **REQ-CMD-005 MUST:** Reboot und Update erfolgen nur nach expliziter Aktion.
- **REQ-CMD-006 MUST:** Statusdaten bleiben nutzbar, wenn nur das Command-Backend
  ausfällt.

## Sicherheit, Betrieb und Qualität

- **REQ-SEC-001 MUST:** Secrets erscheinen niemals in Logs, Exceptions,
  Diagnostics, Entityzuständen oder -attributen.
- **REQ-SEC-002 MUST:** Keine echte Infrastrukturinformation wird im Repository
  gespeichert.
- **REQ-OPS-001 MUST:** Setup, Unload, Reload und Task-Cancellation hinterlassen
  keine Listener oder Hintergrundtasks.
- **REQ-OPS-002 MUST:** Netzwerkfehler führen zu korrekter Availability und
  automatischer Erholung ohne Log-Spam.
- **REQ-QUA-001 MUST:** Der in [[../03-development/quality-gates|Quality Gates]]
  definierte Gate ist vor Merge und Release grün.
- **REQ-DOC-001 MUST:** Installation, Konfiguration, Entities, Datenaktualisierung,
  Grenzen, Removal und Troubleshooting sind öffentlich dokumentiert.

## Native Backend `0.2`

- **REQ-BCK-001 MUST:** Das native Backend läuft mit identischem Anwendungscode
  als Home-Assistant-Add-on und eigenständiger Container.
- **REQ-BCK-002 MUST:** Hosts besitzen eine vom Anzeigenamen unabhängige UUID und
  werden persistent in SQLite verwaltet.
- **REQ-BCK-003 MUST:** Das Backend erzeugt einen persistenten ED25519-Schlüssel;
  die API liefert ausschließlich den öffentlichen Schlüssel aus.
- **REQ-BCK-004 MUST:** Statusprüfung, Update und Reboot werden als persistente,
  asynchrone Jobs ausgeführt. Mutierende Jobs sind je Host serialisiert.
- **REQ-BCK-005 MUST:** Update und Reboot besitzen immer genau ein explizites
  Hostziel. Ein fehlendes oder unbekanntes Ziel schlägt vor Ausführung fehl.
- **REQ-BCK-006 MUST:** Der APT-Provider erkennt Updates und Rebootbedarf auf
  Debian/Ubuntu; weitere Paketmanager werden hinter einem Protocol ergänzt.
- **REQ-BCK-007 MUST:** Benutzerdefinierte Tasks werden strukturiert gespeichert.
  Shellausführung ist eine explizit sichtbare, validierte Entscheidung.
- **REQ-BCK-008 MUST:** Der Execution Adapter wertet Prozess-Exit-Code,
  Ansible-Taskstatus und Warntext getrennt aus. Ein privater Callback liefert
  exakt ein validiertes JSON-Resultat; Freitext ist ausschließlich Joblog.
- **REQ-BCK-009 MUST:** Alle eingebauten Aktionen verwenden dieselbe idiomatische
  Python-Interpreter-Erkennung. `Test connection` prüft SSH, Python/Facts und
  non-interactive sudo; kein fester Python-Pfad wird vorausgesetzt.
- **REQ-BCK-010 MUST:** `check_updates` ermittelt Facts, aktualisiert den APT-Cache,
  liest Updates locale-stabil und prüft Rebootbedarf in getrennten Phasen. Leere
  Update- und Security-Mengen sowie `changed=false` sind erfolgreiche Ergebnisse.
- **REQ-API-001 MUST:** Die HTTP-API stellt Health, Info, Hosts, Aktionen, Jobs,
  begrenzte Jobausgabe, Public Key und Custom Tasks versioniert bereit.
- **REQ-API-002 MUST:** Standalone-Zugriffe benötigen ein API-Token. Secrets,
  Authorization Header und vollständige fremde Prozessausgaben werden nicht
  geloggt oder ungefiltert zurückgegeben.
- **REQ-HA-001 MUST:** Der Config Flow bietet Native Backend und Semaphore an und
  migriert bestehende `0.1`-Einträge ohne Verlust.
- **REQ-HA-002 MUST:** Entities hängen ausschließlich von Application Protocols
  und typisierten Domainmodellen ab, nicht von Provider-Payloads oder Pfaden.
- **REQ-HA-003 MUST:** Jobstatus und Custom Tasks erscheinen dynamisch, ohne dass
  ein Neustart oder eine statische Entity-Liste nötig ist.
- **REQ-HA-004 MUST:** Aktueller Backendzustand, letzter Job und historisch letzter
  fehlgeschlagener Job sind getrennte Zustände. Hub und Hosts veröffentlichen nur
  kompakte Jobmetadaten; vollständige Jobausgabe gelangt weder in Entity-
  Attribute noch Diagnostics oder Recorder.
- **REQ-ADD-001 MUST:** Das Add-on verwendet Home Assistant Ingress, läuft ohne
  Host-Netzwerk und ohne Docker-Socket und fordert keine unnötigen Privilegien.
- **REQ-UI-001 MUST:** Die Management-UI funktioniert am Server-Root und unter
  einem beliebigen Ingress-Prefix; Assets und Requests verwenden relative URLs.
- **REQ-UI-002 MUST:** Alle UI-Aktionen zeigen Loading, Erfolg oder einen
  verständlichen Fehler. Standalone tauscht das Token einmalig gegen eine
  kurzlebige opaque HttpOnly-Session; Ingress gibt es nicht an den Browser weiter.
  Cookie-basierte und Ingress-Mutationen bleiben per CSRF geschützt.
- **REQ-UI-003 MUST:** Update, Reboot und Custom Tasks erfordern eine explizite
  Bestätigung. Automatisierte UI-Tests verwenden ausschließlich synthetische
  Execution Adapter und starten keine echte Hostaktion.
- **REQ-UI-004 MUST:** Standalone unterscheidet sichtbar zwischen nicht verbunden,
  verbindend und verbunden. Eine gültige UI-Session überlebt F5 und lädt Daten
  automatisch neu. Disconnect, Sessionablauf sowie `401` entfernen geschützte
  Daten aus Zustand und DOM, ohne den API-Token persistent zu speichern.
- **REQ-UI-005 MUST:** Standalone-Sessions besitzen acht Stunden absolute und 60
  Minuten Idle-Lifetime, liegen nur im Backend-Arbeitsspeicher und verwenden ein
  `HttpOnly`, `SameSite=Strict`, pfadbegrenztes sowie bei HTTPS `Secure` Cookie.
  External API bleibt Bearer-authentifiziert; Ingress erzeugt keine UI-Session.
- **REQ-UI-006 MUST:** Solange mindestens ein Job `queued` oder `running` ist,
  aktualisiert die UI Jobs und Hosts automatisch mit höchstens einem Poller.
  Terminalzustände stoppen schnelles Polling; Fehler verwenden begrenzten Backoff.
- **REQ-UI-007 MUST:** `#/jobs/<job-id>` öffnet im Standalone- und Ingress-Modus
  dieselbe routbare Jobansicht. Der Hash enthält nie Zugangsdaten; Log und
  Metadaten benötigen eine gültige UI-Session beziehungsweise Ingress-Auth.

## Status-Payload `0.1`

Der Status-Provider liefert ein JSON-Objekt, dessen Keys technische Host-IDs und
dessen Werte Hostobjekte sind. Generisches Beispiel:

```json
{
  "node-01": {
    "checked_at": "2026-01-15T12:00:00Z",
    "distribution": "Example Linux",
    "distribution_version": "1.0",
    "host": "node-01",
    "hostname": "example-node",
    "kernel": "1.0.0-generic",
    "reboot_required": false,
    "security_updates": 2,
    "status": "critical",
    "updates": 5
  }
}
```

Der Top-Level-Key ist kanonisch. Ein abweichendes `host`-Feld wird nicht
stillschweigend als neue Identität übernommen. Die genaue Validierungsentscheidung
wird beim Parser in Tests festgeschrieben.
