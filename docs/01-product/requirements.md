---
title: Produktanforderungen
status: accepted
updated: 2026-08-20
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
