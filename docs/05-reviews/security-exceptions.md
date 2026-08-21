---
title: Security-Ausnahmen
status: active
updated: 2026-08-20
tags: [review, security, dependencies]
---

# Security-Ausnahmen

Ausnahmen sind Teil des Quality Gates, nicht dessen Umgehung. Jede Ausnahme hat
Quelle, Begründung, Kompensation, Owner und Ablaufdatum. Nach Ablauf schlägt der
Gate fehl, bis die Ausnahme entfernt oder neu bewertet wurde.

## SE-2026-001 – Home-Assistant-Teststack `cryptography 48.0.1`

| Feld | Wert |
| --- | --- |
| Advisory | `PYSEC-2026-3552`, `PYSEC-2026-3553`, `PYSEC-2026-3554` |
| Fix | `cryptography >=49.0.0`, für einen Fund `>=50.0.0` |
| Quelle | `homeassistant 2026.8.2` und dessen transitive Abhängigkeiten |
| Integration Runtime | keine eigene `cryptography`- oder sonstige Manifest-Dependency |
| Bewertung | Test-/Plattformabhängigkeit; ein Override bricht den getesteten HA-Lock |
| Kompensation | keine Verarbeitung eigener Schlüssel/Zertifikate; CI bleibt aktuell; Dependabot wöchentlich |
| Owner | Projektmaintainer |
| Ablauf | 2026-09-15 |
| Status | offen, akzeptiert bis Ablauf |

`make audit` ignoriert ausschließlich diese drei IDs. Beim nächsten kompatiblen
Home-Assistant-/Testplugin-Update wird neu gelockt und geprüft. Sobald der Lock eine
gefixte Version enthält, müssen alle drei Ignore-Argumente und diese Ausnahme im
selben Pull Request entfernt werden.
