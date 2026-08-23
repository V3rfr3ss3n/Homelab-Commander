---
title: ADR-0006 Standalone UI Session
status: accepted
updated: 2026-08-22
tags: [architecture, adr, backend, security, ui]
---

# ADR-0006: Standalone UI Session

## Kontext

Die öffentliche Native API verwendet einen langlebigen Bearer Token. Die erste
Standalone-UI hielt diesen Token ausschließlich im JavaScript-Arbeitsspeicher.
Das vermied Browserpersistenz, verlor aber bei jedem F5 den Authzustand. Eine
Persistenz des API-Tokens in Web Storage, URL oder lesbarem Cookie würde das
Schadenspotenzial von XSS und lokalen Browserartefakten erhöhen.

Ingress besitzt bereits die Supervisor-Vertrauensgrenze und braucht keine zweite
Anwendungssession. Home Assistant und externe Clients müssen unverändert Bearer
verwenden können.

## Optionen

1. Bearer Token weiter nur im JavaScript-Speicher halten und Reload verlieren.
2. Bearer Token im Browser persistent speichern.
3. Token einmalig gegen eine kurzlebige, opaque, serverseitige UI-Session in
   einem HttpOnly Cookie tauschen.

## Entscheidung

Option 3 wird nur für die Standalone Management UI umgesetzt:

- `POST /ui-api/auth/login` prüft den API-Token mit konstantem Vergleich und
  erzeugt die Session-ID mit `secrets.token_urlsafe()`.
- Nur die Session-ID liegt im Cookie; der API-Token wird nie zurückgegeben.
- Sessions leben pro Backend-Prozess im Speicher, maximal acht Stunden absolut
  und maximal 60 Minuten ohne Aktivität.
- Das Cookie ist `HttpOnly`, `SameSite=Strict`, auf `/ui-api` begrenzt und bei
  HTTPS zusätzlich `Secure`.
- Mutierende UI-Requests benötigen trotz SameSite weiterhin den im UI-Dokument
  ausgelieferten CSRF-Token.
- F5 prüft `GET /ui-api/auth/session` und lädt bei Erfolg den zentralen
  Dashboard-Snapshot neu. Logout widerruft die Session und löscht das Cookie.
- `/api/v1` bleibt ausschließlich Bearer-authentifiziert. Ingress überspringt die
  Standalone-Session und vertraut weiterhin Supervisor plus CSRF.

## Konsequenzen

- F5 bleibt innerhalb derselben kurzlebigen Management-Session verbunden.
- Browser- oder Backend-Neustart kann die Session beenden; persistente Sessions
  sind für `0.2` ausdrücklich nicht vorgesehen.
- Mehrere Backend-Prozesse würden Sticky Sessions oder einen gemeinsamen Store
  benötigen. Der aktuelle Container startet genau einen API-Prozess.
- HTTPS hinter einem Reverse Proxy muss das ursprüngliche Scheme vertrauenswürdig
  an Uvicorn weitergeben, damit das `Secure`-Flag gesetzt wird.
- Ein gestohlener Session-Cookie ist zeitlich begrenzt, bleibt aber bis Logout
  oder Ablauf schützenswert. CSP, HttpOnly, SameSite, CSRF und kurze Laufzeiten
  bilden die gestaffelte Abwehr.

## Links

- [[../overview|Architekturübersicht]]
- [[../../04-operations/security-and-privacy|Security und Privacy]]
- [[../../01-product/requirements|Produktanforderungen]]
- [[0005-native-backend-boundary]]
