---
title: Native Check Updates E2E Review
status: accepted
updated: 2026-08-22
tags: [review, backend, ansible, apt, e2e]
---

# Native Check Updates E2E Review

## Anlass und Beweislage

Ein manueller Lauf bewies SSH-Key-Authentifizierung und einen erfolgreichen
damaligen `Test connection`. Der anschließend ausgelöste `check_updates`-Job
endete als `failed`. Die zur Analyse bereitgestellte Ausgabe wurde ausschließlich
lokal ausgewertet; Deployment-Adresse, Hostname und Benutzerdaten wurden weder in
Code noch Dokumentation übernommen.

## Root Cause

Es scheiterte kein Remote-Task. Facts wurden zuvor erfolgreich gelesen. Auch der
erste sichtbare Paket-Task `ansible.builtin.command` mit `apt list --upgradable`
meldete `CHANGED` und Remote-`rc=0`. Seine relevante Ausgabe bestand aus der
normalen `Listing...`-Zeile und einer Warnung zur nicht stabilen APT-CLI. Die
Interpreter-Discovery-Warnung war ebenfalls nicht fatal.

Der erste tatsächliche Fehler lag unmittelbar danach in der strukturierten
Ergebnisverarbeitung. `ansible` verwendet für Ad-hoc-`command` standardmäßig den
`minimal`-Callback und schreibt bewusst menschenlesbares
`host | CHANGED | rc=0 >>` statt JSON. Der alte Parser suchte dennoch nach einem
JSON-Objekt und erzeugte deshalb `invalid_ansible_output`. Der Ansible-Prozess
selbst hatte Exit-Code `0`; der Backend-Parser machte den Job anschließend
kontrolliert zu `failed`.

## Entscheidung und Implementierung

- Ein privater Ansible-stdout-Callback liefert pro isoliertem Ein-Host-Lauf exakt
  ein markiertes Envelope mit `event` und objektförmigem `result`.
- Das Backend akzeptiert ein Ergebnis nur bei Prozess-Exit `0`, Event `ok` und
  genau einem validen Envelope. Warnungen und technische Ausgabe bleiben Log.
- Das Inventory setzt für alle Aktionen `ansible_python_interpreter=auto_silent`.
  Es gibt weder einen festen `/usr/bin/python`-Pfad noch hostbezogene Sonderfälle
  oder eine neue Persistenzannahme.
- `Test connection` prüft nacheinander Ping, minimale Facts/Python und ein
  harmloses `true` mit `become`. Damit gelten dieselben Interpreter- und
  sudo-Annahmen wie für `check_updates`.
- `check_updates` besitzt getrennte Phasen für Facts, idempotenten APT-Refresh,
  locale-stabile Paketliste und Reboot-Datei. Jeder Phasenfehler erhält einen
  stabilen Code; Python-, sudo- und APT-Lock-Fehler werden gesondert erkannt.
- Der Debian-Parser akzeptiert leere Ergebnisse, normale Updates, Security
  Updates und abweichende Repository-Namen. Es wird kein `grep` verwendet.
- Die UI zeigt verständliche Fehlertexte und lässt das redigierte, auf 64 KiB
  begrenzte technische Joblog weiterhin abrufbar.

Diese Korrektur ändert weder REST-Vertrag noch Persistenzmodell,
Sicherheitsgrenze, Dependency-Richtung oder Produktionsabhängigkeiten. Ein ADR
war deshalb nicht erforderlich.

## Verifikation

Die automatisierte Matrix deckt ab:

1. Debian-Facts mit erkanntem `/usr/bin/python3`;
2. keinen vorausgesetzten `/usr/bin/python`-Symlink;
3. Interpreter-Warnung im Log;
4. erfolgreiche Resultate trotz Warnungen;
5. APT-Liste ohne Updates;
6. normale Updates;
7. Security Updates;
8. null Security-Treffer ohne Fehler;
9. vorhandene Rebootdatei;
10. fehlende Rebootdatei;
11. APT-Lock-Klassifikation;
12. sudo-Fehler;
13. fehlenden Python-Interpreter;
14. ungültige oder mehrdeutige strukturierte Ergebnisse;
15. Prozess-Exit ungleich null;
16. echtes Ansible-`failed`-Event;
17. konsistente `auto_silent`-Inventory-Strategie für Connection und Check.

Zusätzlich wurde der Callback synthetisch mit `ansible` gegen `localhost` und
einem harmlosen `printf` ausgeführt. Das Resultat enthielt Event `ok`, Modul-`rc=0`
und den erwarteten stdout-Wert. Dieser Test kontaktierte keinen Remote-Host.

## Restrisiken und manuelle Wiederholung

Die Anzahl der Updates stammt weiterhin aus dem menschenlesbaren, aber durch
`LC_ALL=C` stabilisierten APT-Output. Diese Abhängigkeit bleibt im Debian-Provider
gekapselt und durch typische Ausgaben regressionsgetestet. Security-Zuordnung ist
eine best-effort Erkennung anhand des Repository-Namens; unbekannte Namen führen
zu null Security Updates, niemals zum Jobabbruch.

Der reale Zielhost wurde nach dem Fix bewusst nicht kontaktiert. Die manuelle
Abnahme soll ausschließlich `Test connection` und `Check updates` wiederholen,
Jobstatus, Snapshot und Log prüfen. `Update` und `Reboot` bleiben ausdrücklich
außerhalb dieser Abnahme.
