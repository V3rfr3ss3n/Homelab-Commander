---
title: Abnahme
status: accepted
updated: 2026-08-22
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

## Zusatzabnahme `0.2.0-dev`

1. Native und Semaphore sind im Config Flow getrennt auswählbar.
2. Ein `0.1`-Eintrag migriert ohne Verlust oder neue Entity-IDs zu Semaphore.
3. App und Compose starten denselben Backend-Anwendungskern mit persistentem
   `/data`; ein Neustart erhält Hosts, Jobs und SSH-Key.
4. Host-CRUD verwendet unveränderliche UUIDs. Das API liefert niemals den Private
   Key und erzwingt für dessen Datei Modus `0600`.
5. Actions liefern `202` und einen Job; kein HTTP-Request wartet auf Ansible.
6. Update/Reboot/Custom Tasks scheitern ohne exaktes Hostziel. Mutationen
   desselben Hosts sind serialisiert.
7. Update meldet Rebootbedarf, startet aber keinen Reboot.
8. Shell-Tasks sind ohne Deployment-Opt-in nicht anlegbar; Command Tasks nutzen
   ein Argumentarray.
9. Home Assistant zeigt native Job-/Health-Entities und neue Custom Tasks
   dynamisch, ohne Entity-Code für die Provider zu duplizieren.
10. Ingress enthält Host-, Task-, Job- und Public-Key-Verwaltung, gibt das
    API-Token nicht an den Browser und schützt Mutationen per CSRF.
11. Container/App besitzen weder Docker-Socket noch Host-Netzwerk oder unnötige
    Mounts/Capabilities.
12. Das vollständige Quality Gate prüft Integration und Backend gemeinsam.
13. Ein echter Headless-Chromium-Test bedient Connect, Public-Key-Copy sowie
    Host-/Task-Anlage im Standalone-Modus und prüft sichtbare Auth-Fehler.
14. Derselbe Browser-Test lädt UI-Assets und API-Aufrufe unter einem synthetischen
    Ingress-Prefix; kein Request fällt auf den Server-Root zurück.
15. Standalone zeigt vor Authentifizierung und nach Disconnect eindeutig
    `Not connected`. Eine gültige kurzlebige HttpOnly-Session überlebt Reload und
    lädt alle geschützten Daten automatisch; Ablauf oder `401` setzt den sicheren
    Loginzustand wieder her. Der API-Token liegt in keinem Browserspeicher/Cookie.
16. Native Ansible-Läufe liefern Daten über einen privaten JSON-Callback. Warnings
    bleiben im technischen Joblog und können einen erfolgreichen Task nicht in
    `failed` umdeuten.
17. `Test connection` validiert SSH, automatische Python-3-Erkennung, minimale
    Distribution-Facts und non-interactive sudo mit derselben Inventory-Strategie
    wie `check_updates`.
18. `check_updates` behandelt keine Updates, keine Security Updates, fehlende
    `reboot-required`-Datei und unveränderten APT-Cache als Erfolg. Python-, sudo-,
    APT-Lock- und Phasenfehler erscheinen als verständlicher stabiler Fehlercode.
19. Jobs wechseln in der UI ohne manuellen Refresh von `queued` über `running` in
    `success` oder `failed`. Hosts und Dashboard werden bei Abschluss aktualisiert;
    ohne aktive Jobs sowie nach Disconnect läuft kein schneller Poller.
20. Backend Connectivity bleibt online, wenn nur ein historischer Job fehlschlug;
    Latest Job und Latest Failed Job zeigen unabhängig Typ, Zustand und Zeit.
21. Hub und Host Entities enthalten ausschließlich kompakte Jobmetadaten. Weder
    vollständiger Log noch Authorization-Daten gelangen in State, Attribute,
    Recorder oder Diagnostics.
22. `#/jobs/<job-id>` zeigt Metadaten und redigierten Log in Standalone und unter
    synthetischem Ingress-Prefix. Ohne Standalone-Session wird erst authentifiziert
    und anschließend derselbe Job geöffnet; keine URL enthält ein Token.
23. Abschluss von Check, Update, Reboot und Custom Task aktualisiert Jobs,
    Queuezählung und Hostzustand ohne manuellen Home-Assistant-Reload.
24. Ein Native-Hub zeigt nur **Hosts prüfen** als globale manuelle Aktion; ein
    Semaphore-Hub behält **Hosts prüfen** und **Status aktualisieren**, weil dort
    zwei getrennte Templates angesprochen werden.
25. Native registriert für Administratoren **Homelab Updates** in der
    Home-Assistant-Seitenleiste. Die Hauptansicht zeigt Onlinezustand, Hosts,
    Queuezählung, letzten Job und letzten fehlgeschlagenen Job.
26. **Log öffnen** lädt einen begrenzten redigierten Joblog erst auf Klick über
    Home Assistants authentifizierte WebSocket-Verbindung. Nicht-Administratoren
    werden abgewiesen; Token und Log erscheinen weder im Statusstream noch in
    Browser Storage oder Panel-Konfiguration.
27. Sobald ein globaler Check terminal `success`, `failed` oder `cancelled` ist,
    wechselt das Panel aus **Prüfung läuft…** zurück zu **Hosts prüfen**, ohne auf
    einen späteren periodischen Coordinator-Poll zu warten.
