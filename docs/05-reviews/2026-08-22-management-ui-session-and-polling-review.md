---
title: Management UI Session and Polling Review
status: accepted
updated: 2026-08-22
tags: [review, backend, ui, security, polling, playwright]
---

# Management UI Session and Polling Review

## Befund

Zwei unabhängige UX-Probleme hatten dieselbe fehlende Lifecycle-Schicht:

- Standalone hielt den Bearer Token nur in JavaScript und verlor ihn bei F5.
- Jobs wurden nach dem Enqueue einmal geladen und blieben ohne manuellen Refresh
  sichtbar auf `queued` oder `running`, obwohl das Backend bereits terminal war.

Das Backend, die persistente Queue und der strukturierte Ansible-Callback waren
nicht Ursache. Insbesondere darf ein kompletter `check_updates`-Job mehrere
`HOMELAB_UPDATES_RESULT`-Marker enthalten: Facts, APT-Refresh, Paketliste und
Rebootstatus sind vier getrennte Ansible-Aufrufe, die jeweils genau einen Marker
validieren. Dieses Verhalten blieb unverändert und erhielt einen Regressionstest.

## Session-Architektur

Standalone sendet den API-Token einmalig mit CSRF an
`POST /ui-api/auth/login`. Das Backend verwendet denselben konstanten Vergleich
wie die External API, erzeugt mit `secrets.token_urlsafe(32)` eine opaque ID und
speichert ausschließlich deren Zeitstempel im Prozessspeicher. Der Browser erhält
nur die ID als Cookie:

- `HttpOnly`
- `SameSite=Strict`
- `Path=/ui-api`
- `Secure`, sobald das Request-Scheme HTTPS ist
- acht Stunden absolute Lifetime
- 60 Minuten Idle Timeout
- kein persistentes Cookie-Ablaufdatum

`GET /ui-api/auth/session` stellt F5 wieder her und startet denselben zentralen
`refreshDashboard()` wie der sichtbare Refresh-Button. Logout widerruft den
Serverzustand, löscht das Cookie und leert das UI. Ablauf oder ungültige IDs
antworten mit `401` und führen zu `Not connected`. Backend-Neustart verwirft alle
Sessions bewusst; persistente Sessions sind für `0.2` nicht vorgesehen.

Die Grenzen bleiben disjunkt:

- Home Assistant und externe Clients: Bearer Token auf `/api/v1`
- Standalone UI: opaque HttpOnly-Session auf `/ui-api`
- Ingress UI: Supervisor-Authentifizierung ohne Standalone-Session

Ein Bearer Header öffnet `/ui-api` nicht, und ein UI-Cookie öffnet `/api/v1`
nicht. Alle UI-Mutationen prüfen weiterhin `X-CSRF-Token`. CSP, same-origin
Assets, `Cache-Control: no-store` und Fetch `cache: no-store` bleiben aktiv.

## Live-Aktualisierung

Der zentrale vollständige Refresh lädt Info, Hosts, Public Key, Custom Tasks und
Jobs. Ein gezielter Live-Refresh lädt nur Hosts und Jobs. Nach einer Action wird
der zurückgegebene Queuejob sofort gerendert und danach zentral abgeglichen.

Solange mindestens ein Job `queued` oder `running` ist, existiert höchstens ein
Timer mit 1,5 Sekunden Intervall. Bei temporären Fehlern steigt das Folgeintervall
auf drei und fünf Sekunden; sichtbare Daten bleiben stehen und die UI meldet
einmalig Fehler sowie Erholung. Bei Terminalzustand, Disconnect oder `pagehide`
stoppt der Poller. Eine wiederhergestellte Session startet ihn nach F5 erneut,
falls der erste Snapshot aktive Jobs enthält.

Aktive Action-Buttons zeigen `Running…`. Ein aktiver mutierender Job sperrt in der
Darstellung Update, Reboot und Custom Tasks desselben Hosts. Diese Sperre ist nur
Feedback; Queue und Hostlock im Backend bleiben die Security-/Konsistenzgrenze.
Nach Erfolg oder Fehler werden Jobliste, Hosts und Dashboard gemeinsam neu
gerendert. Phasenspezifische Fehlercodes erscheinen als verständliche Kurztexte.

## Automatisierter Nachweis

Die fünf Chromium-Szenarien prüfen unter anderem:

- initiales `Not connected`, Login, leeres Tokenfeld und geladene Daten;
- opaque Cookieflags und fehlenden Token in Cookie, URL, DOM und Web Storage;
- F5-Recovery mit Hosts, Public Key und Jobs ohne erneute Token-Eingabe;
- serverseitigen Logout und weiterhin getrennten Zustand nach folgendem Reload;
- Sessionablauf und ungültigen Cookie mit sicherem Loginzustand;
- Ingress-Prefix, Supervisor-Grenze und CSRF ohne Standalone-Session;
- `queued → running → success` für Check Updates und Test Connection;
- automatische Hostdaten nach erfolgreichem Check;
- automatische verständliche Failed-Darstellung und Dashboard-Zähler;
- genau einen gleichzeitig laufenden Poll, Stopp im Terminalzustand und bei
  Disconnect sowie Wiederaufnahme nach Reload.

API-/Unit-Tests decken zusätzlich absolute/Idle-Lifetime, Collision Handling,
Revoke, HTTP-/HTTPS-Cookieflags, CSRF, Authgrenzentrennung und Ingress-Deaktivierung
der Login-Endpunkte ab.

## Gate-Ergebnis

- Ruff Format/Lint: grün
- Mypy strict: grün
- Pytest inklusive Chromium: `239 passed`
- Line Coverage: `98.18 %`
- Branch Coverage: `95.30 %`
- Dependency Audit: keine unbekannte Schwachstelle; drei dokumentierte Ausnahmen
- Security Exceptions und Privacy Scan: grün

Alle Jobs und Hosts in Tests sind synthetisch. Es wurde keine reale SSH-, Update-
oder Reboot-Aktion ausgeführt.

## Spätere Option

Für `0.3` können Server-Sent Events oder WebSockets den Live-Refresh ersetzen.
Die aktuelle Trennung zwischen vollständigem Dashboard-Refresh, gezieltem Live-
Snapshot und persistentem Jobmodell lässt diesen Austausch ohne Änderung der
Execution- oder Entity-Grenze zu.
