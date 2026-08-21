---
title: Release und Veröffentlichung
status: proposed
updated: 2026-08-20
tags: [operations, release, hacs, public]
---

# Release und Veröffentlichung

## Voraussetzungen für Öffentlichkeit

- Git-Repository und GitHub-Owner festgelegt
- README, Lizenz, Contributing und Security Policy vollständig
- gesamte Historie auf Secrets und Infrastruktur geprüft
- Repositorybeschreibung, Topics, Issues und Security Advisories aktiviert
- Manifest enthält echte öffentliche Dokumentations- und Issue-URLs, keine
  Platzhalter
- Branding ist generisch und enthält keine privaten Assets

Der Codeowner ist `@V3rfr3ss3n`. Der Entwicklungsstand verwendet weiterhin
reservierte Manifest-URLs unter `example.invalid`, solange das Zielrepository
unbekannt ist. Das ist kein Releasewert: `make release-check` schlägt absichtlich
fehl, bis die öffentlichen URLs gesetzt wurden.

## HACS

Es befindet sich genau eine Integration unter `custom_components/`. Alle zur
Laufzeit benötigten Dateien liegen innerhalb des Integrationsordners. `hacs.json`
liegt im Root und enthält mindestens einen Namen sowie die tatsächlich unterstützte
Home-Assistant-Mindestversion.

Zunächst wird das Repository als HACS Custom Repository getestet. Eine spätere
Aufnahme in HACS Defaults ist eine eigene Milestone-Entscheidung und benötigt
unter anderem ein öffentliches aktives GitHub-Repository, HACS-/Hassfest-Checks,
Branding und einen vollständigen GitHub Release.

## Releaseablauf

1. Version und Changelog/Release Notes vorbereiten.
2. Vollständigen Quality Gate auf sauberem Checkout ausführen.
3. Releaseartefakt reproduzierbar bauen und Inhalt prüfen.
4. In isolierter Home-Assistant-Testinstanz installieren und Abnahme durchführen.
5. Signierten/geschützten Tag und GitHub Release erstellen.
6. HACS-Installations- und Upgradepfad erneut prüfen.
7. Bekannte Einschränkungen und Supportfenster veröffentlichen.

Keine Veröffentlichung erfolgt automatisch allein durch Merge auf den
Defaultbranch, bis der Releaseprozess nachweislich stabil ist.

## Versionierung

SemVer wird verwendet. Vor `1.0.0` dürfen Contracts noch bewusst brechen, aber nur
mit Release Notes und Migrationspfad für persistierte Config Entries. Das Manifest,
das Release-Tag und die Release Notes müssen dieselbe Version beschreiben.
