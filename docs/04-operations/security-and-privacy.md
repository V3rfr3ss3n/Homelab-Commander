---
title: Security und Privacy
status: accepted
updated: 2026-08-23
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
| privater SSH-Key verlässt Backend | persistente Datei `0600`, API liefert nur Public Key |
| Command Injection | strukturierte `argv`, kein Shell-Aufruf; Shell-Modus separat und standardmäßig aus |
| parallele Hostmutation | persistente Queue plus Lock je kanonischer Host-UUID |
| fremder UI-Request | Supervisor Ingress beziehungsweise HttpOnly-Session, SameSite und CSRF für Mutationen |
| XSS/Tokenabfluss aus UI | externe same-origin Assets, restriktive CSP; API-Token nur beim Login, Session-Cookie HttpOnly |
| unberechtigter HA-Panelzugriff | Panel und WebSocket-Commands nur für HA-Administratoren; Backend-Token bleibt im Config Entry |
| persistenter Logabfluss in HA | Statusstream ohne Ausgabe; begrenzter redigierter Log nur nach explizitem admin-authentifiziertem Abruf |
| unbegrenzte Prozessausgabe | UTF-8-Normalisierung, NUL-Entfernung, Redaction und 64-KiB-Grenze |

## Logging

Erlaubt sind abstrakte Aktion, technische synthetische Host-ID, HTTP-Statusklasse
und Task-ID, sofern erforderlich. Verboten sind Token, Header, Config-Dumps,
vollständige URLs mit Query/Benutzerinfo und ungeprüfte Response Bodies.

Backend-Jobausgabe wird nicht in den Prozesslog geschrieben. Sie liegt begrenzt
in SQLite und wird vor Speicherung um Zieladresse und SSH-Benutzer bereinigt.
Paketnamen können betriebliche Informationen enthalten; deshalb ist der
Job-Log-Endpunkt nur authentifiziert erreichbar und gehört nicht in Bugreports.
Der Ansible Adapter liest fachliche Daten ausschließlich aus seinem markierten
JSON-Envelope. Warnungen und stderr bleiben technische Ausgabe; sie werden weder
als Erfolg interpretiert noch ungeprüft in API-Fehlertexte übernommen.
Home Assistant erhält davon nur Job-ID, Typ, Zustand, Zeiten, sicheren Fehlercode
und eine tokenfreie UI-URL. Vollständige Ausgabe wird weder Entityattribut,
Sensorzustand noch Diagnostics-Inhalt. Der `#/jobs/<job-id>`-Hash trägt keine
Credentials; der anschließende Abruf bleibt session-/Ingress-authentifiziert.

Das native Home-Assistant-Panel verwendet ausschließlich Home Assistants
authentifizierte WebSocket-Verbindung. Panel, Statusabonnement, Hostprüfung und
Logabruf verlangen Administratorrechte. Die Panel-Konfiguration enthält nur die
Config-Entry-ID und eine bereits konfigurierte tokenfreie Backend-Basis-URL. Der
Backend-Token bleibt serverseitig im Config Entry und wird vom Native Adapter
verwendet. Statusevents enthalten ausschließlich kompakte Metadaten; der
begrenzte redigierte Log wird nach **Log öffnen** einmalig übertragen, mit
`textContent` gerendert und weder in Entities, Recorder, Diagnostics, DOM-
Attributen noch Browser Storage persistiert.

## Vertrauensgrenzen des nativen Backends

Das API-Token schützt Standalone- und optionale veröffentlichte App-Ports.
Supervisor Ingress authentifiziert den UI-Zugriff; der Browser erhält dabei das
API-Token nicht. Der Ingress-Modus darf nur innerhalb des Supervisor-Netzes
aktiviert werden und wird vom Container-Entrypoint ausschließlich bei vorhandener
`/data/options.json` gesetzt.

Im Ingress-Modus löst das Backend den stabilen internen DNS-Alias `supervisor`
beim Start auf. UI-Dokument, Assets und `/ui-api` akzeptieren ausschließlich
direkte Verbindungen aus dieser aufgelösten Proxy-Adressmenge. Es wird keine
deployment-spezifische Adresse gespeichert. Direkte Zugriffe über einen optional
veröffentlichten Port erhalten keinen Ingress-Vertrauensstatus. Die External API
`/api/v1` bleibt für Home Assistant Core und andere explizite Clients weiter
ausschließlich durch den Bearer Token geschützt.

Die External API `/api/v1` bleibt ausschließlich durch Bearer Token geschützt.
Die Standalone-UI sendet das eingegebene Token einmalig an den Login-Endpunkt und
speichert es weder in URL, DOM-Ausgabe, Local/Session Storage, IndexedDB noch
Cookie. Das Backend erzeugt eine opaque Session-ID mit Systemzufall und hält
Sessionzustand nur im Prozessspeicher. Das Cookie ist `HttpOnly`,
`SameSite=Strict`, auf `/ui-api` begrenzt und bei HTTPS `Secure`. Seine absolute
Lifetime beträgt acht Stunden, der Idle Timeout 60 Minuten.

F5 validiert die vorhandene Session und lädt Backenddaten neu. Disconnect
widerruft sie serverseitig und löscht das Cookie. Ablauf, ungültiger Cookie oder
`401` entfernen geschützte Daten und verlangen den API-Token erneut. Ein Backend-
Neustart verwirft alle Sessions; eine Browser-Neustart-Wiederherstellung ist nicht
garantiert, weil das Cookie bewusst keine persistente Ablaufzeit erhält. Ingress
erzeugt keine solche Session und verwendet weiter Supervisor Auth. Mutationen
beider UI-Modi prüfen zusätzlich den CSRF-Header. Siehe
[[../02-architecture/adr/0006-standalone-ui-session|ADR-0006]].
UI-Dokument und CSRF-Token werden mit `Cache-Control: no-store` ausgeliefert.
JavaScript und CSS kommen als externe same-origin Assets; die Content Security
Policy erlaubt keine Inline-Skripte.

Der Backend-Schlüssel ist eine privilegierte Maschinenidentität. Wird für den
Remote-Account passwortloses `sudo` eingerichtet, ist der Schlüssel entsprechend
wie Root-Zugriff zu behandeln. Hosts sollten einen eigenen Automationsbenutzer,
Netzfilter und keine wiederverwendeten persönlichen Schlüssel erhalten.

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
