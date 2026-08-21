---
title: Quality Gates
status: accepted
updated: 2026-08-20
tags: [development, quality, ci, testing]
---

# Quality Gates

Ein Merge oder Release ist nur bei vollständig grünem Gate erlaubt. `make quality`
ist die kanonische Schnittstelle für lokale Runs und CI. `make release-check`
ergänzt öffentliche URL-/Codeowner-Prüfungen.

## Gate-Stufen

| Stufe | Werkzeug | Blockierendes Kriterium |
| --- | --- | --- |
| Format | Ruff | `ruff format --check .` ohne Diff |
| Lint | Ruff | `ruff check .` ohne ungeklärte Suppression |
| Types | Mypy | Strict Check ohne Fehler |
| Tests | Pytest | alle Unit-/Integrationstests grün |
| Coverage | Coverage.py | mindestens 95 % Lines **und** 95 % Branches, unabhängig geprüft |
| HA validation | Hassfest | Manifest, Services, Übersetzungen und Struktur gültig |
| HACS | HACS Action | Repository als Integration valide |
| Supply chain | Audit-Tool | keine ungeklärte bekannte Schwachstelle oder unzulässige Lizenz |
| Secrets | Gitleaks-artiger Scan | keine Secrets in Arbeitsbaum oder Git-Historie |
| Privacy | Projektpattern | keine reale Infrastruktur oder persönlichen Daten |
| Docs | Markdown/Links | keine kaputten internen Links; öffentliche Anleitung aktuell |

## Testpyramide

1. **Unit:** Parser, Modelle, Zustandsautomat, Redaction und Pure Functions.
2. **Adapter contracts:** gemockte HTTP-Requests/Responses und Fehlerabbildung.
3. **Home Assistant integration:** Config Flow, Coordinator, Registry, Entities,
   Lifecycle, Reauth/Reconfigure und Diagnostics.
4. **Isolierte manuelle Abnahme:** temporäre Home-Assistant-Testinstanz und Fake-
   Backend; niemals ein produktives Homelab.

## Mindest-Testmatrix

- gültige, leere, teilweise und ungültige Statuspayloads
- Integer-/Boolean-/Timestamp-Grenzfälle sowie unbekannte Zusatzfelder
- Timeout, DNS/Connect, TLS, 401/403, 404, 429 und 5xx
- Duplicate Config, Reauth, Reconfigure, Reload und Unload
- neuer, verschwundener und umbenannter Host
- Updates 0, 1 und mehrstellig; Security Updates unabhängig davon
- Task waiting/running/success/failed/error/unknown/timeout/cancel
- Backendausfälle unabhängig voneinander
- Token nicht in Logs, Exceptions, Diagnostics oder Entityattributen

## Dependency Policy

- Runtime- und CI-Dependencies sind exakt oder reproduzierbar gepinnt.
- Dependabot oder Renovate erstellt Updates; CI entscheidet über Kompatibilität.
- Ein Auditfund wird bewertet und dokumentiert. Ein Ignore braucht Ablaufdatum,
  Begründung und Referenz.
- Release Actions werden auf unveränderliche Commit-SHAs gepinnt, soweit praktikabel.

## Ausnahmen

Eine Ausnahme ist nur über eine dokumentierte, zeitlich begrenzte Entscheidung mit
Owner, Risiko, Kompensation und Ablaufdatum zulässig. Coverage wird nicht durch
`# pragma: no cover` erhöht, außer nach begründeter Review einer technisch nicht
erreichbaren Zeile.

## Referenzziel

Das Projekt orientiert sich an Home Assistants Integration Quality Scale: Gold als
Nutzerqualitätsbaseline, ergänzt um strikte Typisierung und vollständig asynchrone
Abhängigkeiten. Nicht anwendbare Core-Regeln werden im späteren
`quality_scale.yaml` ausdrücklich begründet.
