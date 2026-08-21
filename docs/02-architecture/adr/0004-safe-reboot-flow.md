---
title: ADR-0004 Sicherer Neustart-Flow
status: accepted
updated: 2026-08-20
tags: [architecture, adr, safety, reboot, repairs]
---

# ADR-0004: Sicherer Neustart-Flow

## Kontext

Ein Hostneustart unterbricht Dienste und darf weder versehentlich noch als
implizite Folge eines Updates ausgelöst werden. Die native Update Entity bietet
keinen integrationsspezifischen Checkbox- oder Dialogparameter für „danach neu
starten“. Auch die Farbe einer Entity wird vom Home-Assistant-Frontend und Theme
bestimmt, nicht vom Python-Backend.

## Entscheidung

- Der Reboot-Button verwendet `ButtonDeviceClass.RESTART`, ein Alert-Icon und die
  Kategorie `config`.
- Er ist nur verfügbar, wenn der aktuelle Snapshot `reboot_required: true`
  meldet, und während konkurrierender Update-/Reboot-Tasks gesperrt.
- Neustartbedarf erzeugt einen nicht persistenten, behebbaren Repair-Hinweis.
- Der Repair-Flow prüft Entry und aktuellen Hoststatus erneut, warnt vor der
  Unterbrechung und startet erst nach explizitem Submit den limitierten Reboot.
- Weder Task-Erfolg noch Update-Installation lösen automatisch einen Neustart aus.

## Konsequenzen

- Der Nutzer erhält eine native, auffällige und bestätigungspflichtige Abfrage.
- Dashboard-Autoren können Farben zusätzlich im jeweiligen Card-Theme festlegen;
  die Integration verspricht keine frontendübergreifend feste Rotfärbung.
- Automationen können den Button-Service weiterhin direkt aufrufen, aber nur bei
  gemeldetem Neustartbedarf. Solche Serviceaufrufe besitzen keinen UI-Dialog und
  bleiben Verantwortung des Automation-Autors.
