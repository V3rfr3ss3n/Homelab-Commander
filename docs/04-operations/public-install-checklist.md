---
title: Öffentliche Installations-Checkliste
status: active
updated: 2026-08-23
tags: [operations, release, hacs, app, checklist]
---

# Öffentliche Installations-Checkliste

Diese Checkliste wird für jeden Release Candidate in einer frischen, isolierten
Home-Assistant-OS-Testinstanz ausgeführt. Es werden ausschließlich synthetische
Hosts und reservierte Beispielwerte verwendet. Keine Prüfstufe kontaktiert ein
reales Zielsystem oder startet Update beziehungsweise Reboot.

## Vorbedingungen

- [ ] Quality, HACS, Hassfest, CodeQL, Secret Scan und Container-Build sind grün.
- [ ] App-, Manifest-, Image- und Release-Version stimmen überein.
- [ ] Das generische GHCR-Image ist ohne Registry-Anmeldung pullbar.
- [ ] Sein Manifest enthält `linux/amd64` und `linux/arm64`.
- [ ] Alle zum Image gehörenden GHCR-Pakete sind öffentlich sichtbar.
- [ ] Release Notes nennen Entwicklungsstatus, Grenzen und Upgradehinweise.

## Frische Installation

- [ ] Repository als HACS Custom Repository hinzufügen.
- [ ] **Homelab Commander** Integration installieren und Home Assistant neu starten.
- [ ] Dasselbe Repository im App Store hinzufügen.
- [ ] App-Karte, Icon, Dokumentation und Konfigurationsschema prüfen.
- [ ] **Homelab Commander Backend** App ohne Registry-Credentials installieren.
- [ ] Zufälligen Testtoken konfigurieren und App starten.
- [ ] Ingress-Seite und öffentliche SSH-Key-Anzeige öffnen.
- [ ] Die laufende lokale App wird im Native Config Flow automatisch erkannt;
      weder Identifier noch Port oder URL werden eingegeben.
- [ ] Nur wenn internes DNS nicht funktioniert, den Backend-Port im isolierten
      Testnetz als dokumentierten Fallback freigeben.
- [ ] Native Integration mit demselben Token einrichten.
- [ ] Backendzustand, Hauptpanel und Backend-Ingress-Eintrag prüfen.

## Sichere Funktionsprüfung

- [ ] Nur einen synthetischen, gemockten oder vollständig isolierten Testhost
      anlegen.
- [ ] **Test connection** und **Check updates** für den isolierten Testhost
      ausführen; keine Update-Installation oder Reboot-Aktion starten.
- [ ] Einen erzeugten Testjob öffnen und den begrenzten, redigierten Log prüfen.
- [ ] Fehlende/ungültige Authentifizierung ohne Secret-Leak prüfen.
- [ ] Neustart von App und Home Assistant überlebt persistente `/data`-Daten.
- [ ] API-Token, Private Key und Logs erscheinen nicht in Diagnostics oder
      Browser Storage.
- [ ] Entfernung von Integration und App getrennt prüfen; `/data` nur nach
      ausdrücklicher Entscheidung löschen.

## Ergebnis

- [ ] Datum, getestete Version und Ergebnis ohne IPs, Hostnamen, Tokens oder
      unredigierte Logs in den Release Notes festhalten.
- [ ] Abweichungen als öffentliche Issues mit ausschließlich synthetischen
      Reproduktionsdaten dokumentieren.
