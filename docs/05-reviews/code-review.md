---
title: Code Review
status: accepted
updated: 2026-08-20
tags: [review, quality, checklist]
---

# Code Review

## Reviewer-Reihenfolge

### 1. Verhalten

- Löst die Änderung das beschriebene Problem und nur dieses?
- Sind Akzeptanzkriterien, Fehlerfälle und Nutzertexte vollständig?
- Bleiben Config Entry und Entity-IDs migrationsstabil?

### 2. Architektur

- Stimmt die Abhängigkeitsrichtung?
- Bleibt Backendwissen in Adaptern?
- Gibt es unnötige globale Zustände, I/O in Entity Properties oder Leaks beim
  Unload?
- Braucht die Entscheidung ein ADR oder aktualisiert sie ein bestehendes?

### 3. Home Assistant

- Werden aktuelle Config-Flow-, Coordinator-, Runtime-Data- und Entity-Patterns
  korrekt verwendet?
- Sind Availability, Reauth, Reconfigure, Übersetzungen und Diagnostics korrekt?
- Sind Polling und parallele Commands begrenzt?

### 4. Sicherheit und Privacy

- Können Tokens oder Response Bodies in Logs/Exceptions gelangen?
- Sind URLs, Redirects, TLS, Zielhost und Timeouts sicher behandelt?
- Sind alle Beispiele synthetisch und ist der Diagnostics-Datensatz minimal?

### 5. Tests und Wartbarkeit

- Testen die Tests Verhalten und Negativpfade statt Interna?
- Sind Netzwerk, Zeit und Zufall deterministisch?
- Ist neue Komplexität typisiert, benannt und dokumentiert?
- Ist die Coverage echt oder durch Ausschlüsse kosmetisch erhöht?

### 6. Abschluss

- Quality Gate grün und keine ungeklärten Warnungen
- README/Docs/TODO/ADR aktualisiert
- keine generierten, lokalen oder geheimen Dateien im Diff
- Reviewer hinterlässt `approve`, konkrete Änderungsanforderungen oder klar
  gekennzeichnete nicht-blockierende Hinweise

Für Reviews kann [[../templates/code-review-template|die Vorlage]] kopiert werden.
