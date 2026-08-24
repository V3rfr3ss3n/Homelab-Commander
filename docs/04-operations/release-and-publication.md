---
title: Release und Veröffentlichung
status: active
updated: 2026-08-23
tags: [operations, release, hacs, ghcr, public]
---

# Release und Veröffentlichung

## Öffentliche Quellen

Der Codeowner ist `@V3rfr3ss3n`. Das öffentliche Quellrepository ist
[`V3rfr3ss3n/Homelab-Commander`](https://github.com/V3rfr3ss3n/Homelab-Commander);
Fehlerberichte werden im
[Issue Tracker](https://github.com/V3rfr3ss3n/Homelab-Commander/issues) und
Sicherheitslücken ausschließlich über
[private Security Advisories](https://github.com/V3rfr3ss3n/Homelab-Commander/security/advisories/new)
eingereicht. Reservierte `example.invalid`-Werte bleiben nur in synthetischen
Beispielen und Test-Fixtures zulässig.

Vor einer Veröffentlichung müssen README, Lizenz, Contributing, Security Policy,
Release Notes, Privacy Audit und die
[[public-install-checklist|öffentliche Installations-Checkliste]] aktuell sein.

## Container-Pipeline

`.github/workflows/container.yml` verwendet die auf eine Commit-SHA gepinnten
offiziellen Home-Assistant-Builder-Actions. Der Workflow setzt
[[../02-architecture/adr/0008-public-container-publishing|ADR 0008]] um:

| Ereignis | AMD64/AArch64 bauen und prüfen | In GHCR veröffentlichen |
| --- | --- | --- |
| Pull Request | ja | nein |
| Push auf `main` | ja | nein |
| manueller Lauf, `publish=false` | ja | nein |
| manueller Lauf von `main`, `publish=true` | ja | ja |
| Tag `v<version>` auf einem `main`-Commit | ja | ja |

Eine veröffentlichte Version muss exakt mit
`addon/homelab_updates/config.yaml` übereinstimmen. Die Pipeline erzeugt native
AMD64-/AArch64-Images und den von der App referenzierten generischen Multi-Arch-
Manifest-Tag. Es gibt keinen automatischen `latest`-Tag für Development-Releases.
Pull Requests besitzen keine Package-Schreibrechte. Publish-Jobs nutzen nur das
eingebaute kurzlebige `GITHUB_TOKEN` mit `packages: write`; ein PAT ist weder
nötig noch erlaubt.

Jeder Build prüft Image-Labels, Port `8099`, Volume `/data`, Healthcheck,
Ansible/OpenSSH und die unprivilegierte PID-1-UID `10001`. Nach Veröffentlichung
prüft ein frischer Job ohne Registry-Anmeldung das Multi-Arch-Manifest, den
anonymen Pull und denselben Laufzeitvertrag.

## Öffentliche Development-Veröffentlichung

Nach Merge der Pipeline auf `main`:

1. In GitHub **Actions → Container → Run workflow** öffnen.
2. Branch `main`, Version `0.3.0-dev.0` und `publish=true` wählen.
3. Den Lauf bis zur Manifest-Veröffentlichung und zum anonymen Gate abwarten.
4. Nur bei der allerersten Package-Veröffentlichung: Auf der GitHub-Profilseite
   unter **Packages** jedes neu erzeugte zugehörige
   Containerpaket öffnen. Für Architekturimages und generischen Manifest-Eintrag
   unter **Package settings → Danger Zone → Change visibility** jeweils
   **Public** wählen. Die öffentliche Sichtbarkeit kann nicht wieder auf privat
   zurückgestellt werden.
5. Falls Schritt 4 nötig war, den zuvor am anonymen Gate fehlgeschlagenen
   Workflow erneut ausführen. Es werden keine Registry-Credentials an Endnutzer
   verteilt.
6. Das Ergebnis auf einem abgemeldeten beziehungsweise frischen Client prüfen:

   ```bash
   docker logout ghcr.io || true
   docker buildx imagetools inspect \
     ghcr.io/v3rfr3ss3n/homelab-updates-backend:0.3.0-dev.0
   docker pull \
     ghcr.io/v3rfr3ss3n/homelab-updates-backend:0.3.0-dev.0
   ```

Erst ein grünes anonymes Gate und die frische Home-Assistant-Installation gelten
als Veröffentlichung. Ein `401`/`403` wird nicht durch einen Benutzerlogin oder
ein Token im App-Setup umgangen.

## HACS und Branding

Es befindet sich genau eine Integration unter `custom_components/`; alle
Laufzeitdateien und das lokale `brand/` liegen darin. Eine Aufnahme in HACS
Defaults ist eine spätere Milestone-Entscheidung und erfordert einen vollständigen
öffentlichen Release.

Home Assistant ab 2026.3 kann die lokalen Custom-Integration-Assets verwenden.
Ein separater Brands-PR ist deshalb derzeit nicht erforderlich. Die HACS-
Repositorykarte kann bis zum nächsten vollständigen Release beziehungsweise
Cache-Reload noch einen Platzhalter zeigen. Dateipfade und Austauschverfahren
stehen in [[../03-development/branding|Branding und Icons]].

## Releaseablauf

1. SemVer-Version gleichzeitig in Python-Projekt, Integrationsmanifest und App-
   Konfiguration setzen; Changelogs und Release Notes aktualisieren.
2. Vollständiges Quality Gate auf sauberem Checkout ausführen.
3. Versionierten Container über den geschützten Tag- oder manuellen Pfad
   veröffentlichen; anonymes Manifest-/Pull-Gate abwarten.
4. GitHub Release erstellen und das HACS-Artefakt prüfen.
5. [[public-install-checklist|Öffentliche Installations-Checkliste]] in einer
   isolierten Home-Assistant-Testinstanz vollständig durchführen.
6. HACS-Installations- und Upgradepfad erneut prüfen und bekannte Einschränkungen
   veröffentlichen.

SemVer wird verwendet. Vor `1.0.0` dürfen Contracts bewusst brechen, aber nur mit
Release Notes und Migrationspfad für persistierte Config Entries. Manifest,
App-Konfiguration, Container-Tag und Release-Tag müssen dieselbe Version
beschreiben.
