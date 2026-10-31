---
title: Documentation link gate review
status: draft
updated: 2026-10-30
tags: [review, documentation, quality]
---

# Documentation link gate review

T-033 übernimmt die Dokument-Linkprüfung aus dem Backlog. `make docs` prüft
Dateiziele ohne Netzwerkzugriff und ist Teil von `make quality`. Es werden keine
Produktionsabhängigkeiten, API-Verträge oder Laufzeitverhalten verändert; ein
neues Architektur-ADR ist deshalb nicht erforderlich.

Geprüfte Grenzen: relative Markdown-/Bildlinks, Referenzdefinitionen,
Wikilinks mit Alias und impliziter `.md`-Endung, URL-encodierte Dateinamen,
Codebeispiele und ausschließlich öffentliche Linkziele. Anker und externe URLs
sind ausdrücklich nicht Bestandteil der Prüfung. Lokale, ignorierte Dateien
werden zusätzlich aus dem Docker-Buildkontext ausgeschlossen.

## Prüfstand

Der vollständige lokale Lauf verwendete wegen der Sandbox einen beschreibbaren
uv-/Ansible-Temporärpfad und lief für lokale Testserver und Chromium außerhalb
der Sandbox:

```sh
UV_CACHE_DIR=/tmp/homelab-uv-cache UV_NO_SYNC=1 ANSIBLE_LOCAL_TEMP=/tmp/homelab-ansible-tmp PYTEST_ADDOPTS='--timeout=30' make quality
```

- Ruff Format und Lint: bestanden.
- Mypy: 43 Laufzeitmodule bestanden; der neue Checker wurde zusätzlich mit
  `.venv/bin/mypy --strict scripts/check_doc_links.py` erfolgreich geprüft.
- Pytest: **287 bestanden**, einschließlich der drei neuen Checker-Tests und
  der Browserprüfungen; keine Tests übersprungen.
- Coverage: **98,18 % Lines**, **95,32 % Branches**; beide Mindestwerte bestanden.
- `make docs`: keine fehlenden Dateiziele.
- `make audit`: fehlgeschlagen mit `Expired security exceptions: SE-2026-001`.
  Der nachfolgende `pip-audit`-Aufruf wurde dadurch nicht ausgeführt; aktuelle
  Schwachstellenfreiheit ist nicht verifiziert.
- `UV_CACHE_DIR=/tmp/homelab-uv-cache UV_NO_SYNC=1 make privacy`: separat bestanden,
  da der Auditfehler diesen Schritt im Gesamtlauf verhindert.
- `git diff --check`: bestanden; Diff und neue Dateien auf URLs, persönliche
  Pfade, Infrastrukturwerte und Secrets geprüft. Nur synthetische Testdaten.

Der erste Sandbox-Lauf scheiterte am schreibgeschützten uv-Cache, der nächste an
Ansible-Temporärdateien. Weitere Sandbox-Versuche wurden wegen blockierender
Test-Fixture-Threads abgebrochen; der oben dokumentierte Lauf ersetzt diese
Versuche vollständig. Die zuvor neu angelegte virtuelle Umgebung wurde mit
`uv sync --frozen` aus dem unveränderten Lockfile wiederhergestellt.

Der vorbestehende Ablauf von SE-2026-001 blockiert weiterhin den gesamten Gate;
diese Änderung verlängert die Ausnahme nicht. T-033 bleibt bis zum vollständigen
grünen Gate offen. Kein Merge, Release oder öffentliches CI-Ergebnis wird
behauptet. Hassfest, HACS, Container-Build und Gitleaks-Historienscan wurden lokal
nicht ausgeführt; das Gitleaks-Binary ist hier nicht installiert.
