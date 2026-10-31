---
title: Dokumentation und Wiki
status: active
updated: 2026-10-31
tags: [development, documentation, wiki, obsidian]
---

# Dokumentation und Wiki

## Fakten und aktuelle Hoheit

Prüfstand 2026-10-31: Das verbundene GitLab-Projekt ist öffentlich, das Wiki ist
aktiviert und enthält laut API keine Seiten. Es gibt einen aktivierten Push-Mirror;
sein gemeldeter Status ist `finished`. Zieladressen und Infrastrukturmetadaten
werden nicht in diese Dokumentation übernommen. Eine erfolgreiche vollständige
Synchronisierung oder gesondert geschützte Wiki-Bereiche sind damit nicht belegt.

GitLab enthält bisher keine eigene CI-Konfiguration und die Pipeline-API meldete
keine Läufe. Diese Änderung ergänzt nur den vorhandenen `make quality`-Vertrag als
MR-/Hauptbranch-Job; GitHub-Validatoren und Veröffentlichungsregeln bleiben bestehen.

Bis zu einer ausdrücklich freigegebenen und verifizierten Migration bleiben
`README.md`, `CONTRIBUTING.md`, `docs/` und ADRs die versionierte Quelle der Wahrheit.
Der [Index](../README.md) bietet GitLab-/GitHub-/Obsidian-kompatible Navigation.
Es werden keine Inhalte entfernt, Wiki-Seiten veröffentlicht, Rechte geändert
oder weitere Synchronisationsprozesse aktiviert.

## Inventory and history

| Bereich | Inhalt und Pflege |
| --- | --- |
| Root README, CONTRIBUTING, SECURITY, CHANGELOG | öffentliche Installation, Mitarbeit, Security-Kontakt und Änderungen |
| `00-project/` | Vision, Roadmap, aktuelles TODO und Backlog |
| `01-product/` | Anforderungen und Abnahme |
| `02-architecture/` | Architektur, REST-Vertrag, ADR-Index und neun vorhandene ADRs; Entscheidungshistorie erhalten |
| `03-development/` | Code-Regeln, Qualität, Workflow, Foundation, Branding und Dokumentationshoheit |
| `04-operations/` | Backendbetrieb, Migration, Installation, Release und Privacy |
| `05-reviews/` | laufende Review-/Risiko-/Ausnahmeregister und datierte Prüfnachweise |
| `templates/`, Glossar, Referenzen | wiederverwendbare Vorlagen und Nachschlagewissen |

Datierten Reviewdateien liegt ein bestimmter Code-/Prüfstand zugrunde. Sie sind
historische Evidenz, auch wenn älteres Frontmatter `active` sagt. Aktuelle Regeln
kommen aus Security, ADRs und den im Index verlinkten Fachdokumenten. Historische
Ergebnisse nie als heutigen Teststatus ausgeben. Neue Nachweise separat datieren.

## Sichere Wiki-Übernahme: vorbereitet, nicht aktiviert

Ziel ist Wiki-First-Navigation ohne konkurrierende gepflegte Textkopien. Die
konkrete Übernahme bleibt offen, bis folgende Bedingungen erfüllt sind:

1. Projektowner bestätigt Ziel, Sichtbarkeit, Leserechte und veröffentlichbaren
   Umfang anhand tatsächlicher GitLab-Berechtigungen. Ein Unterordner `internal`
   schützt nichts; vertrauliche Organisationsinformationen benötigen einen
   separat berechtigten Bereich außerhalb dieses öffentlichen Projektwissens.
2. Öffentliche Nutzerthemen und technische Projektdokumentation getrennt
   navigieren. Beide bleiben frei von echten Infrastrukturwerten, auch in einem
   privaten Wiki. Repository-regelnde Dateien und reproduzierbare Build-/Test-
   Anweisungen bleiben beim Code.
3. Vorhandene Inhalte inventarisieren und gegen das freigegebene Ziel abgleichen.
   ADRs mit Nummern/Historie, Frontmatter und relative Obsidian-Links erhalten.
   Auf dem hier leeren Wiki ist noch kein Abgleich oder Import erfolgt.
4. Zunächst eine freigegebene Wiki-Startseite mit Links auf die kanonischen
   versionierten Dokumente einrichten und ihre Navigation/Leserechte prüfen.
   Vollständige Inhaltsmigration nur mit festgelegter alleiniger Pflegequelle,
   Rückweg und geprüftem Markdown-/Obsidian-Linkmapping.
5. Erst nach erfolgreichem Abgleich README-Verweise umstellen; Quellen niemals
   vor erfolgreicher Migration entfernen. Externe Wiki-Links und Sichtbarkeit
   separat prüfen: `make docs` validiert nur lokale Dateiziele.
6. Keine weitere Veröffentlichung oder bidirektionale Synchronisation aktivieren.
   Eine spätere öffentliche Übernahme verwendet ausschließlich freigegebene,
   geprüfte Inhalte und den bestehenden GitLab-geführten Mechanismus.

Die neue Navigation ist sofort nutzbar. Die externe Migration ist eine offene
Freigabeentscheidung; sie wird nicht als abgeschlossen dargestellt.
