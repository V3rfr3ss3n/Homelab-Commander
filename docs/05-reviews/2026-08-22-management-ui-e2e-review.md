---
title: Management UI E2E Review
status: superseded
updated: 2026-08-22
tags: [review, backend, ui, playwright, ingress]
---

# Management UI E2E Review

> [!NOTE]
> Der historische Auth-/Reload-Abschnitt wurde durch
> [[2026-08-22-management-ui-session-and-polling-review]] abgelöst.

## Anlass

Ein manueller E2E-Smoke zeigte eine vollständig gerenderte Management-UI, deren
Buttons keine Reaktion auslösten. Der Test enthielt deployment-spezifische Daten;
diese wurden weder in Code noch in Dokumentation oder Fixtures übernommen.

## Root Cause

Die UI lag als normaler mehrzeiliger Python-String vor. Eine JavaScript-Sequenz
mit `\n` wurde beim Erzeugen der HTTP-Antwort bereits durch Python in einen echten
Zeilenumbruch umgewandelt. Dieser stand danach innerhalb eines einzeiligen
JavaScript-Strings. Chromium brach das komplette Script mit einem Syntaxfehler ab;
alle global referenzierten Handler fehlten. Der bisherige Syntaxcheck untersuchte
nur Python-Quelltext und konnte den ausgelieferten Response-Body nicht bewerten.

## Entscheidung und Umsetzung

- HTML, JavaScript und CSS sind getrennte same-origin Assets.
- JavaScript liegt als Raw String vor und bindet Events nach `DOMContentLoaded`.
- Relative Asset- und API-URLs funktionieren am Server-Root sowie unter einem
  beliebigen Supervisor-Ingress-Prefix.
- Standalone nutzt Bearer-Authentifizierung; Ingress liest ohne Browser-Token und
  verlangt CSRF für Mutationen.
- Jede Aktion setzt einen sichtbaren Loading-, Erfolgs- oder Fehlerzustand.
- Update, Reboot, Löschen und Custom Tasks verlangen eine Bestätigung.
- Eine restriktive Content Security Policy blockiert Inline-Skripte.

## Automatisierter Nachweis

Headless Chromium verbindet sich mit einem echten lokalen Uvicorn-Prozess. Der
Standalone-Test prüft alle fünf initialen API-Requests, Public-Key-Anzeige und
Clipboard, Host-/Task-Anlage, Tokenentfernung aus dem Eingabefeld und eine
sichtbare `401`-Fehlermeldung. Er klickt außerdem Test Connection, Check Updates
und einen bestätigten Custom Task gegen den synthetischen Executor und prüft die
unterschiedlichen v1-Pfade. Ein zweiter Test setzt einen synthetischen
Ingress-Prefix vor die ASGI-App und beweist, dass Assets und API-Requests unter
diesem Prefix bleiben, CSRF-geschützte Hostanlage funktioniert und die Ingress-
Action-Route verwendet wird.

Die Tests verwenden generische Daten und einen synthetischen Execution Adapter.
Sie starten weder SSH/Ansible noch Update oder Reboot. Auch die simulierten
Connection-, Check- und Custom-Task-Jobs verlassen den Testprozess nicht.

## Gate-Ergebnis

- Exakter CLI-Start `uv run --frozen homelab-updates-backend` plus Chromium:
  `Connected`, Public Key sichtbar, keine Page Errors.
- `make quality`: 209 Tests grün; Lines `98.11 %`, Branches `95.18 %`; Ruff,
  Mypy strict, Dependency Audit und Privacy Scan grün.
- `docker compose config --quiet`: grün mit synthetischer Konfiguration.
- Native-Runtime-Audit: Backend, Dockerfile, Compose und App enthalten weder
  Semaphore-Abhängigkeit noch einen fremden Ansible-Pfad. Inventory, ED25519-Key,
  SQLite und Jobs gehören dem nativen Backend.

Der nach der UI-Änderung angeforderte Container-Build und Healthcheck konnten
nicht wiederholt werden, weil weder der ausgewählte Docker-Desktop-Context noch
der Standard-Context einen Docker-API-Socket bereitstellten. Docker Desktop wurde
kontrolliert zu starten versucht, blieb aber ohne Daemon und meldete sich danach
als nicht laufend. Unverifiziert sind daher exakt:

```bash
docker build --tag homelab-updates-backend:ui-e2e .
docker run --detach --name homelab-updates-ui-e2e \
  --env HUL_API_TOKEN='<synthetic-token>' \
  homelab-updates-backend:ui-e2e
docker inspect --format '{{json .State.Health}}' homelab-updates-ui-e2e
```

Der Container wurde im vorherigen Native-Backend-Review bereits erfolgreich
gebaut und auf Health/UID geprüft; diese Aussage ersetzt nicht die ausstehende
Wiederholung für die aktuelle UI-Änderung. T-020a bleibt deshalb offen.

## Standalone Session UX

Die UI unterscheidet nun explizit `Not connected`, `Connecting…` und `Connected`.
Vor dem Connect ist nur ein Login-Placeholder sichtbar; Dashboard, Public Key,
Hosts, Tasks, Jobs und Log sind verborgen und geleert. Dadurch wird fehlende
Authentifizierung nicht mehr als leeres Backend fehlinterpretiert.

Ein erfolgreicher Connect leert und deaktiviert das Tokenfeld, zeigt die
geschützten Daten und bietet Standalone einen Disconnect-Button. Reload,
Disconnect sowie jede `401`-/`403`-Antwort löschen Token und geschützte Daten aus
dem UI-Zustand. Chromium prüft Erstaufruf, Connect, simulierten Sessionablauf,
erneuten Connect, Reload und Disconnect. Browser-Speicher, Cookies und URL bleiben
weiterhin unbenutzt.
