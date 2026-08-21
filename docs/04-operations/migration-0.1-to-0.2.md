---
title: Migration 0.1 nach 0.2
status: active
updated: 2026-08-21
tags: [operations, migration, home-assistant]
---

# Migration von `0.1` nach `0.2`

## Bestehender Semaphore-Eintrag

Beim ersten Laden ergänzt die Integration `backend_type=semaphore` und erhöht das
Config-Entry-Schema auf Version 2. URLs, Token, Projekt, Template-IDs, Unique ID,
Geräte-IDs und Entity-IDs bleiben erhalten. Es ist keine manuelle Neueinrichtung
nötig. Vor dem Upgrade trotzdem ein Home-Assistant-Backup erstellen.

Ein Providerwechsel innerhalb desselben Config Entry erfolgt bewusst nicht. Für
das native Backend wird ein zweiter Eintrag angelegt; nach erfolgreicher Abnahme
kann der alte Semaphore-Eintrag entfernt werden. So gibt es keinen stillen Wechsel
von Hostidentitäten oder Aktionszielen.

## Umstieg auf das native Backend

1. App oder Standalone-Container starten und API-Token konfigurieren.
2. Public Key auf ausschließlich synthetisch dokumentierte Weise auf jedem
   Zielhost autorisieren; echte Werte bleiben außerhalb des Repositorys.
3. Hosts im Management-UI anlegen und Connection-/Statuschecks ausführen.
4. In Home Assistant einen neuen Homelab-Updates-Eintrag mit Provider `native`
   anlegen.
5. UUID-basierte Devices und Entities prüfen, bevor Semaphore entfernt wird.

Native UUIDs sind absichtlich nicht mit alten Inventory-IDs gleichgesetzt. Eine
automatische Entity-Registry-Umschreibung wäre mehrdeutig und findet nicht statt.

## Rückweg

Der alte Semaphore-Eintrag kann parallel erhalten oder neu angelegt werden. Das
native Datenvolume wird beim Entfernen des HA Config Entry nicht verändert. Ein
Rollback der Integration ändert die native SQLite-Datenbank nicht, ältere
Integrationsversionen verstehen aber native Config Entries nicht.
