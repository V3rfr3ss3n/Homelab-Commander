---
title: ADR-0002 Public by default
status: accepted
updated: 2026-08-20
tags: [architecture, adr, privacy, security]
---

# ADR-0002: Public by default

## Kontext

Das Projekt soll später öffentlich und über HACS installierbar werden. Homelab-
Metadaten können Geräte, Netze und Angriffsflächen offenlegen. Eine nachträgliche
Bereinigung entfernt Daten nicht zuverlässig aus der Git-Historie.

## Entscheidung

Jeder Repository-Inhalt muss ab dem ersten Commit veröffentlichbar sein. Reale
Konfiguration, Diagnosen, Hostnamen, Netzadressen und Zugangsdaten werden niemals
committed. Dokumentation und Tests nutzen synthetische, generische Daten.

Konfiguration findet ausschließlich in Home Assistants Config Entry statt.
Diagnostics werden mit Allowlist- und Redaction-Tests abgesichert. Secret Scan und
ein projektspezifischer Privacy-Scan sind blockierende CI-Schritte.

## Konsequenzen

- Entwickler benötigen lokale, ignorierte Konfiguration oder vollständige Mocks.
- Ein Leak blockiert sofort den Release und löst Rotation plus History-Audit aus.
- Screenshots und Support-Anhänge brauchen dieselbe Prüfung wie Code.
- Die ursprüngliche Planung mit realen Beispielen wird nicht ins Repository
  kopiert.
