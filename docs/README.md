---
title: Wissensspeicher
status: active
updated: 2026-08-21
tags: [project, index]
---

# Homelab Updates – Wissensspeicher

Dieser Ordner ist zugleich technische Projektdokumentation und Obsidian Vault.
Er enthält nur veröffentlichbare Informationen. Lokale Infrastrukturwerte gehören
nicht hierher.

## Einstieg

- [[00-project/vision-and-scope|Vision und Scope]] – Zielbild und Grenzen
- [[01-product/requirements|Produktanforderungen]] – priorisierte Anforderungen
- [[02-architecture/overview|Architektur]] – Komponenten und Abhängigkeiten
- [[00-project/todo|TODO]] – aktuelle, geordnete Arbeitsliste
- [[03-development/quality-gates|Quality Gates]] – Definition eines grünen Builds
- [[04-operations/security-and-privacy|Security und Privacy]] – öffentliche
  Repository-Regeln und Bedrohungsmodell
- [[04-operations/native-backend|Native Backend]] – Docker, Add-on, SSH und Betrieb
- [[04-operations/migration-0.1-to-0.2|Migration 0.1 → 0.2]] – kompatibler Umstieg
- [[02-architecture/native-api|Native API]] – versionierter REST-Vertrag
- [[references|Referenzen]] – maßgebliche externe Dokumentation

## Bereiche

| Ordner | Zweck |
| --- | --- |
| `00-project` | Vision, Roadmap, Backlog und aktuelle Arbeit |
| `01-product` | Anforderungen und Abnahme |
| `02-architecture` | Systementwurf und Architecture Decision Records |
| `03-development` | Technik, Code-Regeln, Tests und Arbeitsweise |
| `04-operations` | Security, Releases und Veröffentlichung |
| `05-reviews` | Review-Checklisten und Projektrisiken |
| `templates` | Wiederverwendbare Dokumentvorlagen |

## Dokumentationsregeln

1. Ein Dokument hat Frontmatter mit `title`, `status`, `updated` und `tags`.
2. Statuswerte sind `draft`, `proposed`, `active`, `accepted`, `superseded` oder
   `archived`.
3. Entscheidungen werden als ADR festgehalten; offene Arbeit steht im TODO oder
   Backlog, nicht versteckt im Fließtext.
4. Änderungen am Verhalten aktualisieren Anforderungen, Abnahme und README im
   selben Pull Request.
5. Echte Umgebungsdaten sind auch in privaten Notizen innerhalb dieses Ordners
   verboten. Siehe [[04-operations/security-and-privacy]].

## Quellen der Wahrheit

Bei Widersprüchen gilt folgende Reihenfolge:

1. Security-/Privacy-Regeln
2. akzeptierte ADRs
3. Produktanforderungen und Abnahmekriterien
4. Architektur- und Entwicklungsdokumentation
5. Roadmap, Backlog und TODO

Die ursprüngliche Fachskizze bleibt eine Eingabe, ist aber keine Repository-Datei
und keine höhere Autorität als diese bereinigte Dokumentation.
