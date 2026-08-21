---
title: Abnahme
status: accepted
updated: 2026-08-20
tags: [product, acceptance, release]
---

# Abnahme `0.1.0`

## Happy Path

1. Nutzer installiert die Custom Integration aus einem Release.
2. Nutzer öffnet **Settings → Devices & services → Add integration**.
3. Nutzer trägt generische Backend- und Status-Konfiguration ein.
4. Beide Verbindungen und der Payload werden validiert.
5. Beliebig viele vom Payload gelieferte Hosts erscheinen als Devices.
6. Ein Host mit fünf Updates, zwei Security Updates und ohne Rebootbedarf zeigt
   genau diese Fakten sowie eine verfügbare native Update Entity.
7. `Install` startet die konfigurierte Updateaktion nur für diesen Host.
8. Während der Task läuft, zeigt die Entity `in_progress`.
9. Nach Backend-Erfolg wird der Status neu geladen; nur der neue Payload bestimmt,
   ob das Update verschwunden ist.
10. Meldet dieser Payload `reboot_required: true`, erscheint ein behebbarer
    Repair-Hinweis. Erst dessen bestätigter Flow startet den Neustart.
11. Der Neustartbutton ist ohne Neustartbedarf unavailable und während Update oder
    Neustart gesperrt.

## Fehlerfälle

- Falscher Token startet Reauthentication und legt kein Secret in Logs offen.
- Ungültiges JSON markiert Statusentities unavailable, ohne Home Assistant zu
  destabilisieren.
- Ein ausgefallener Status-Provider macht Command-Entities nicht prinzipiell
  unregistrierbar.
- Ein ausgefallenes Command-Backend lässt vorhandene Statuswerte nutzbar.
- Task `failed`, `error`, Timeout und unbekannter Zustand enden kontrolliert.
- Ein neu auftauchender Host erhält Entities; ein fehlender Host wird nicht
  automatisch gelöscht.
- Setup, Reload und Unload erzeugen keine doppelten Listener oder Tasks.
- Schließen der Neustartabfrage startet keinen Task; ein veralteter Repair-Hinweis
  kann keinen inzwischen unnötigen Neustart auslösen.

## Release Gate

- alle Muss-Anforderungen sind durch Test oder dokumentierte manuelle Abnahme
  nachgewiesen
- Zeilen- und Branch-Coverage der Integrationsmodule mindestens 95 Prozent
- Ruff Format/Lint, Mypy strict, Pytest, Hassfest und HACS Action grün
- Dependency-, License- und Secret-Scan ohne ungeklärten Fund
- englische und deutsche Übersetzungen validiert
- README, Troubleshooting, Removal und Release Notes aktuell
- `rg`-basierter Privacy-Audit sowie Review der Git-Historie durchgeführt
- Installation aus dem erzeugten Releaseartefakt in einer isolierten Testinstanz
  erfolgreich; keine Verbindung zu produktiver Infrastruktur

## Nicht akzeptabel

- manuelle Quellcodeänderung für eine Installation
- echte Umgebung in Fixtures oder Screenshots
- erfolgreiche Taskantwort wird ohne Statusbestätigung als installierter Zustand
  dargestellt
- übersprungene blockierende Checks ohne dokumentierte Ausnahmeentscheidung
