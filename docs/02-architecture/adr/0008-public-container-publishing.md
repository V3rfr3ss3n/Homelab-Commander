---
title: ADR 0008 – Öffentliche Multi-Arch-Container-Veröffentlichung
status: accepted
updated: 2026-08-23
tags: [architecture, adr, container, release, security]
---

# ADR 0008 – Öffentliche Multi-Arch-Container-Veröffentlichung

## Kontext

Die Home Assistant App referenziert ein GHCR-Image. Ein vorhandener Repository-
Eintrag genügt nicht: private oder fehlende Images führen bei öffentlichen
Installationen zu `401`/`403`. AMD64 und AArch64 müssen denselben versionierten
App-Vertrag erhalten, ohne Schreibrechte in Pull-Request-Builds zu verteilen.

## Entscheidung

- Die offiziellen Home-Assistant-Builder-Actions werden auf eine unveränderliche
  Commit-SHA der Version `2026.06.0` gepinnt.
- Pull Requests und normale Pushes auf `main` bauen und prüfen beide nativen
  Architekturen, veröffentlichen aber nichts.
- Ein Tag `v<version>` auf einem Commit von `main` oder ein expliziter manueller
  Lauf von `main` darf veröffentlichen. Die Version muss exakt mit
  `addon/homelab_updates/config.yaml` übereinstimmen.
- Pro Architektur entsteht ein Image; zusätzlich wird der generische
  Multi-Arch-Verweis `ghcr.io/v3rfr3ss3n/homelab-updates-backend:<version>`
  publiziert. Entwicklungsstände erhalten niemals implizit `latest`.
- Veröffentlichung nutzt ausschließlich das eingebaute `GITHUB_TOKEN` mit
  `contents: read` und ausschließlich in Publish-Jobs `packages: write`.
- Ein frischer Job ohne Registry-Credentials prüft Manifest, anonymen Pull,
  Container-Metadaten, Werkzeuge, Healthcheck und unprivilegierte Laufzeit.
- Die einmalige öffentliche Sichtbarkeit der neu erzeugten GHCR-Pakete bleibt
  eine bewusste Maintainer-Aktion in GitHubs Package-Einstellungen.

## Folgen

Die App ist nach erfolgreicher Veröffentlichung auf AMD64 und AArch64 ohne
Registry-Login installierbar. Die erste Veröffentlichung kann zunächst am
anonymen Gate scheitern, bis alle erzeugten Pakete öffentlich geschaltet wurden;
danach wird der Workflow erneut ausgeführt. Es gibt keinen PAT und keinen
öffentlichen Pull-Request-Pfad mit Package-Schreibrechten.

Die Architekturimages und der generische Manifest-Package-Eintrag können in
GitHubs Oberfläche getrennte Sichtbarkeit besitzen. Alle gehören deshalb in die
Release-Checkliste. Signierung und Provenance sind nicht Teil dieser Entscheidung
und werden separat bewertet, bevor dafür zusätzliche Tokenrechte eingeführt
werden.
