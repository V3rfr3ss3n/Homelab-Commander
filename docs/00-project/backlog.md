---
title: Backlog
status: active
updated: 2026-08-20
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

- [ ] Capability-Endpoint für ein zukünftiges Operations Backend definieren
- [ ] zweiter Backend-Adapter als Architekturbeweis
- [ ] Authentifizierungsvarianten jenseits von Bearer Token bewerten
- [ ] Push-Status und Webhooks bewerten

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
