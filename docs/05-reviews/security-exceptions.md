---
title: Security-Ausnahmen
status: active
updated: 2026-10-31
tags: [review, security, dependencies]
---

# Security-Ausnahmen

Ausnahmen sind Teil des Quality Gates, nicht dessen Umgehung. Jede Ausnahme hat
Quelle, Begründung, Kompensation, Owner und Ablaufdatum. Nach Ablauf schlägt der
Gate fehl, bis die Ausnahme entfernt oder neu bewertet wurde.

## Active exceptions

None. `make audit` checks the expiry registry and audits the installed graph
without advisory ignores. Resolved records remain below as history.

## SE-2026-001 – Home-Assistant-Teststack `cryptography 48.0.1`

| Feld | Wert |
| --- | --- |
| Advisory | `PYSEC-2026-3552`, `PYSEC-2026-3553`, `PYSEC-2026-3554` |
| Fix | `cryptography >=49.0.0`, für einen Fund `>=50.0.0` |
| Quelle | gemeinsamer Dev-Lock durch `homeassistant 2026.8.2`; `ansible-core` ist ebenfalls transitiver Consumer |
| Integration Runtime | keine eigene `cryptography`- oder sonstige Manifest-Dependency |
| Backend Runtime | Container überschreibt den transitiven Stand gepinnt mit `cryptography 50.0.0` |
| Bewertung | verbleibt ausschließlich im lokalen/CI-HA-Teststack; ein globaler Override bricht dessen getesteten Lock |
| Kompensation | Produktionsimage nutzt den Fix; Backend-Keyhandling nutzt OpenSSH; CI und Dependabot bleiben aktuell |
| Owner | Projektmaintainer |
| Ablauf | 2026-09-15 |
| Status | resolved 2026-10-31: refreshed HA test graph installs cryptography 50.0.1; all advisory ignores removed |

The original exception expired without renewal. It was removed from the active
registry only after the fixed development and production-only graphs passed an
unfiltered audit. The production image now installs cryptography from `uv.lock`
and no longer overwrites it after sync. The tested development-only Pillow
replacement is documented in [ADR-0010](../02-architecture/adr/0010-secure-test-dependency-replacements.md);
it installs the fixed package and does not ignore vulnerability reports.
