---
title: Technische Grundlage
status: accepted
updated: 2026-08-20
tags: [development, technical, dependencies]
---

# Technische Grundlage

## Stack

- Python `>=3.14.2`; CI verwendet Python 3.14
- Home Assistant `2026.8.2` in der gesperrten Entwicklungsumgebung;
  veröffentlichte Mindestversion `2026.8.0`
- Home Assistant Custom Integration unter
  `custom_components/homelab_updates/`
- Home Assistants gemeinsame aiohttp-Session; keine eigene langlebige Session
- `pytest-homeassistant-custom-component 0.13.356` aus `uv.lock` für isolierte
  Integrationstests
- Ruff für Formatierung und Linting
- Mypy im Strict Mode
- Pytest, Coverage.py und asyncio-Testunterstützung
- Hassfest und HACS Action als repository-spezifische Validatoren

`pyproject.toml` definiert direkte Toolanforderungen, `uv.lock` sperrt den
vollständigen Abhängigkeitsgraph. CI installiert ausschließlich mit
`uv sync --locked`.

## Quellstruktur

```text
custom_components/homelab_updates/
├── __init__.py              # Config entry lifecycle and typed runtime data
├── manifest.json
├── const.py
├── config_flow.py
├── coordinator.py
├── entity.py
├── update.py
├── sensor.py
├── binary_sensor.py
├── button.py
├── diagnostics.py
├── domain/                  # models, task state and capabilities
├── application/             # protocols and use cases
├── adapters/                # status HTTP and Semaphore implementations
└── translations/
    ├── en.json
    └── de.json
```

Kleine Home-Assistant-Plattformmodule bleiben flach. Transportunabhängige Modelle,
Application Services und Backendadapter besitzen eigene Unterpakete.

## Dependencies

Produktion soll möglichst nur Home-Assistant-Core-Funktionen verwenden. Für jede
zusätzliche Runtime Dependency werden Zweck, Lizenz, Maintainer-Aktivität,
Transitivabhängigkeiten, bekannte Schwachstellen und Alternative geprüft. Parser-
Komfort allein rechtfertigt keine Dependency.

## Zeit und Netzwerk in Tests

- keine echten HTTP-Anfragen
- keine echten Tokens oder kopierten Responses
- keine echten Sleeps; Clock/Scheduling kontrollieren
- synthetische Fixtures bilden Erfolgs-, Fehler- und Zukunftsfälle ab
- Contract-Tests prüfen Requestmethoden, relative Pfade, Headerredaction und
  Responseparsing ohne Serverkontakt

## Noch festzulegen

- öffentliche GitHub-Repository- und Support-URLs
- endgültige Semaphore-Kompatibilitätsmatrix nach isolierten Adaptertests
