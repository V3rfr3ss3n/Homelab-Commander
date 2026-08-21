---
title: Security und Privacy
status: accepted
updated: 2026-08-20
tags: [operations, security, privacy]
---

# Security und Privacy

## Schutzziele

- Geheimhaltung von Tokens und Infrastrukturmetadaten
- Integrität der gewählten Zielhosts und Commands
- Verfügbarkeit von Home Assistant trotz Backendfehlern
- Nachvollziehbarkeit ohne sensitive Logs
- sichere Veröffentlichung des vollständigen Repositorys

## Datenklassifizierung

| Klasse | Beispiele | Repository/Logs |
| --- | --- | --- |
| Secret | Token, Authorization Header, private key | niemals |
| Deployment-sensitive | echte URL, IP, Host-/Domainname, Projekt-/Template-ID | niemals |
| Potentially sensitive | Task-ID, Distribution, Kernel, Updatezahl | nur redigierte Diagnostics; Logs sparsam |
| Public synthetic | `node-01`, `example.invalid`, erfundene Payloads | erlaubt |

Auch RFC1918-Adressen können reale Topologie verraten. Dokumentation nutzt daher
bevorzugt reservierte Domains unter `example.invalid`, nicht die Werte eines
Entwicklungsnetzes.

## Bedrohungen und Maßnahmen

| Bedrohung | Maßnahme |
| --- | --- |
| Token in Exception/Log | sichere Exceptionhierarchie, keine Response Bodies, Leakage-Tests |
| falscher Zielhost | kanonische Host-ID, keine Anzeigenamen als Commandziel, Requesttests |
| SSRF/Redirect zu fremdem Ziel | URL-Validierung, dokumentiertes Redirectverhalten, Tests |
| TLS-Abschaltung | nur entry-spezifische Option, Standard `verify_ssl=true`, klare Warnung |
| Command-Replay/Doppelklick | In-progress-Sperre/Idempotenzstrategie pro Host und Aktion |
| endloses Task Polling | monotone Deadline, begrenztes Intervall, Cancellation beim Unload |
| manipuliertes Status-JSON | Größen-/Typvalidierung, unbekannte Felder ignorieren, sichere Fehler |
| Supply-chain-Angriff | wenige Dependencies, Pins, Audit, gepflegte Updateautomation |
| Veröffentlichung echter Daten | Pre-commit/CI Secret- und Privacy-Scan plus Review |

## Logging

Erlaubt sind abstrakte Aktion, technische synthetische Host-ID, HTTP-Statusklasse
und Task-ID, sofern erforderlich. Verboten sind Token, Header, Config-Dumps,
vollständige URLs mit Query/Benutzerinfo und ungeprüfte Response Bodies.

Ein Logeintrag soll genau einmal beim Eintritt in einen Ausfallzustand und einmal
bei Erholung erscheinen. Wiederholtes Polling darf keinen Log-Spam erzeugen.

## Diagnostics

Diagnostics wird per Allowlist gebaut. Token wird vollständig redigiert; URLs
werden von Userinfo, Query und Fragment bereinigt. Host-IDs und Hoststatus werden
bewusst nicht aufgenommen. Enthalten sind nur Integrationsversion, sichere
Konfigurationsmerkmale, Coordinator-Erfolg, Hostanzahl und Anzahl aktiver Tasks.
Tests prüfen das vollständige serialisierte Ergebnis auf Secret- und Host-Leaks.

## Entwicklercheck vor Commit

- `git diff --cached` vollständig lesen
- nach Tokenformaten, `Authorization`, URLs, IPs, Domains, Hostnamen und E-Mail-
  Adressen suchen
- Fixtures und Snapshots manuell auf Herkunft prüfen
- keine `.env`, Home-Assistant-Konfiguration, Diagnostics oder Screenshots
- auch gelöschte Dateien bedenken: bereits committete Daten bleiben in Git

## Incident

Bei möglichem Leak: Veröffentlichung/Release stoppen, betroffene Zugangsdaten
sofort außerhalb dieses Repositorys rotieren, Reichweite inklusive Git-Historie
prüfen, sichere Bereinigung koordinieren und einen knappen Security Record ohne
das Secret erstellen. Das Secret wird niemals zur Beweisführung erneut gepostet.
