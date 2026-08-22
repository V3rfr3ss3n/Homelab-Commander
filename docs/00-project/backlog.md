---
title: Backlog
status: active
updated: 2026-08-22
tags: [project, backlog]
---

# Backlog

Items sind nach Themen gruppiert und noch nicht zur Umsetzung zugesagt. Vor dem
Verschieben ins [[todo|TODO]] braucht jedes Item Akzeptanzkriterien, Abhängigkeiten
und eine Privacy-Prüfung.

## Product

- [ ] letzter Command-Status und Laufzeit je Host
- [ ] Security-only Update als optionale Backend-Capability
- [ ] Paketliste mit begrenzter, datenschutzfreundlicher Darstellung
- [ ] Reparaturhinweise über Home Assistant Repairs
- [ ] Benachrichtigungen nach fehlgeschlagenen oder abgeschlossenen Aktionen
- [ ] Maintenance Mode und Wartungsfenster
- [ ] Hostgruppen ohne Kopplung an konkrete Inventarnamen

## Backends

- [ ] kontrollierbares Job-Cancelling mit persistentem Zustand ergänzen
- [ ] Custom-Task-Policy um Become, Timeout, Bestätigung und optionale
  Host-/Gruppenfreigaben erweitern
- [ ] Authentifizierungsvarianten für externe API-Clients jenseits von Bearer
  Token bewerten; die Standalone UI nutzt bereits eine separate Kurzzeitsession
- [ ] Push-Status und Webhooks bewerten
- [ ] für `0.3` Server-Sent Events oder WebSockets als Ersatz für aktives
  Management-UI-Jobpolling bewerten
- [ ] native TLS-Terminierung bewerten; bis dahin HTTPS über einen Reverse Proxy
- [ ] weitere Package Provider für DNF, Pacman und APK implementieren

## Homelab extensions

- [ ] Backupzustand und explizite Backup-Aktion
- [ ] Snapshot-Workflow vor Updates
- [ ] Proxmox-Host-, VM- und LXC-Beziehungen
- [ ] Container-Updatezustand
- [ ] Service-Health und Zertifikatsablauf

## Developer experience

- [ ] Devcontainer erst nach Messung des lokalen Setup-Aufwands
- [ ] Mutation Testing für Parser und Task-Zustandsautomat
- [ ] Architekturtests für Import-/Abhängigkeitsgrenzen
- [ ] automatisierte Dokument-Linkprüfung

## Abgelehnt oder zurückgestellt

- Direkte SSH-Ausführung in Home Assistant: zu große Credential- und
  Prozessverantwortung.
- Automatische Reboots durch die Integration: widerspricht der expliziten
  Sicherheitsgrenze.
- Reale Backend-Systemtests in öffentlicher CI: nicht reproduzierbar und riskant.
