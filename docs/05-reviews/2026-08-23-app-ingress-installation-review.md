---
title: App Ingress Installation Review
status: active
updated: 2026-08-23
tags: [review, app, ingress, installation, security]
---

# App Ingress Installation Review

## Anlass

Der erste öffentliche App-Store-Test bestätigte anonymen Image-Pull,
Containerstart und Health-Endpunkt. Der Sidebar-Aufruf erreichte das Backend aber
als `GET //` und erhielt `404`. Zusätzlich interpretierte Home Assistant einen
relativen Link der installierten App-Dokumentation als lokalen `/config/docs`-
Pfad. Die realen Installationsdaten und Logs wurden nicht in das Repository
übernommen.

## Root Cause

`ingress_entry` besitzt bereits den Home-Assistant-Standard `/`. Die App setzte
denselben Wert unnötig explizit. Supervisor kombinierte den Ingress-Einstieg mit
dem Root-Slash und leitete `//` statt `/` weiter. Der Backend-Route `@app.get("/")`
war korrekt.

Markdown-Links in der installierten App werden innerhalb Home Assistants und
nicht relativ zum GitHub-Checkout aufgelöst. `../../docs/...` wurde deshalb zu
einem nicht vorhandenen Home-Assistant-Pfad.

## Umsetzung

- `ingress_entry` wurde entfernt; Supervisor verwendet seinen unveränderten
  Standard-Root.
- Ein synthetischer Supervisor-Prefix-Proxy zeichnet die tatsächlich an ASGI
  weitergereichten Pfade auf. Der Browsertest verlangt für den Einstieg exakt
  `/`, verbietet `//` und prüft weiterhin Assets, UI-API, CSRF-Mutation und
  Job-Deep-Link unter dem verschachtelten Prefix.
- Im Ingress-Modus löst das Backend den stabilen internen Alias `supervisor` auf;
  Management-Root, Assets und `/ui-api` akzeptieren nur diese Proxy-Quellen.
  `/api/v1` bleibt separat Bearer-authentifiziert und ist für Home Assistant Core
  erreichbar.
- Installierte App-Dokumente verwenden stabile öffentliche GitHub-URLs.
- README und App-Dokumentation beschreiben HACS-Integration und Backend-App als
  zwei erforderliche, getrennte Komponenten des empfohlenen Native-Setups.
- Die manuelle interne Core-URL wird aus dem installierten App-Identifier
  gebildet; ein Repository-Hash wird nicht fest codiert. Automatischer Discovery-
  Handoff bleibt Backlog.

## Abnahme

Automatisierte Tests verwenden nur synthetische Hosts und einen Fake Executor.
Sie starten weder SSH/Ansible noch Paketupdate oder Reboot. Nach Merge und
Veröffentlichung von `0.2.0-dev.1` bleiben ein App-Update und der erneute reale
Ingress-/Integrations-Smoke gemäß öffentlicher Installations-Checkliste nötig.
