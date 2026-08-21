---
title: Referenzen
status: active
updated: 2026-08-20
tags: [documentation, references, home-assistant, hacs]
---

# Referenzen

Diese Primärquellen wurden beim Architekturentwurf geprüft. `updated` ist das
letzte interne Prüfdatum, nicht das Veröffentlichungsdatum der Quelle. Vor der
Implementierung eines betroffenen Features wird die Quelle erneut geprüft, weil
Home-Assistant-APIs und Qualitätsregeln sich weiterentwickeln.

## Home Assistant

- [Integration manifest](https://developers.home-assistant.io/docs/creating_integration_manifest/)
  – Manifestpflichten, Version, Config Flow, Integration Type und IoT Class
- [Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
  und [Regelkatalog](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/)
  – Qualitätsziel und `quality_scale.yaml`
- [Runtime data](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/runtime-data/)
  – typisiertes `ConfigEntry.runtime_data`
- [Fetching data](https://developers.home-assistant.io/docs/integration_fetching_data/)
  – Coordinator und zentraler Poll
- [Setup failures](https://developers.home-assistant.io/docs/integration_setup_failures/)
  – First Refresh, Retry und Authfehler
- [Update entity](https://developers.home-assistant.io/docs/core/entity/update/)
  – native Update Entity und Install Feature
- [Custom integration localization](https://developers.home-assistant.io/docs/internationalization/custom_integration/)
  – Übersetzungsdateien und Hassfest-Prüfung
- [Testing](https://developers.home-assistant.io/docs/development_testing/)
  – Pytest und Linting im Home-Assistant-Ökosystem
- [Hassfest for custom components](https://developers.home-assistant.io/blog/2020/04/16/hassfest/)
  – Validierung eigener Integrationen

## HACS

- [Publishing integrations](https://hacs.xyz/docs/publish/integration/)
  – Repositorystruktur und Manifestanforderungen
- [General publishing requirements](https://hacs.xyz/docs/publish/start/)
  – öffentliches GitHub-Repository, README, `hacs.json` und Releases
- [HACS GitHub Action](https://hacs.xyz/docs/publish/action/)
  – automatisierte Repositoryvalidierung
- [Default repository requirements](https://hacs.xyz/docs/publish/include/)
  – zusätzliche Anforderungen für eine spätere Aufnahme in HACS Defaults

## Automation Backend

Die Semaphore-API-Dokumentation wird vor Implementierung des Adapters gegen die
unterstützte Versionsmatrix geprüft. Request-/Responseverträge werden danach als
synthetische Contract-Fixtures im Repository festgehalten. Keine Referenz darf
eine URL oder Antwort aus einer realen Installation enthalten.
