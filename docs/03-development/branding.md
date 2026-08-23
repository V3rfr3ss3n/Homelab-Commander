---
title: Branding und Icons
status: active
updated: 2026-08-23
tags: [development, branding, hacs, app]
---

# Branding und Icons

Home Assistant Integration und Home Assistant App werden getrennt verpackt.
Deshalb kann das Icon nicht zuverlässig nur als eine physische Datei im
Repository liegen. Die Integrationsdateien sind die gestalterische Quelle; die
App enthält für ihr eigenes Paket byte-identische Kopien.

## Dateien und Größen

| Zweck | Datei | Größe |
| --- | --- | --- |
| Integration/HACS | `custom_components/homelab_updates/brand/icon.png` | 256 × 256 px |
| Integration HiDPI | `custom_components/homelab_updates/brand/icon@2x.png` | 512 × 512 px |
| App Store Icon | `addon/homelab_updates/icon.png` | 256 × 256 px |
| App Store Logo | `addon/homelab_updates/logo.png` | 512 × 512 px |

Alle Dateien sind quadratische PNGs mit Transparenz. Weil dasselbe quadratische
Motiv als Icon und Logo verwendet wird, braucht die Integration keine zusätzlichen
`logo.png`-Dateien.

## Icon austauschen

1. Das neue Motiv als 256 × 256 PNG nach
   `custom_components/homelab_updates/brand/icon.png` exportieren.
2. Eine echte 512 × 512 Variante nach
   `custom_components/homelab_updates/brand/icon@2x.png` exportieren.
3. Die 256er Datei bytegleich nach `addon/homelab_updates/icon.png` kopieren.
4. Die 512er Datei bytegleich nach `addon/homelab_updates/logo.png` kopieren.
5. `make quality` ausführen. Der Deployment-Test prüft Format, Abmessungen und
   identische Kopien.

Symlinks werden nicht verwendet: GitHub-/HACS-/App-Pakete dürfen die Dateien
unabhängig voneinander erstellen und ausliefern.

## Home Assistant und HACS

Home Assistant ab 2026.3 kann das lokale `brand/` einer Custom Integration
direkt verwenden; ein Pull Request an `home-assistant/brands` ist für dieses
Repository deshalb nicht erforderlich. `hacs.json` enthält bewusst keine
externe Branding-URL.

Ein Platzhalter in der HACS-Repositoryliste kann trotz korrekter lokaler Assets
vorübergehend sichtbar bleiben. Repositorydarstellung, HACS-Cache und das von
Home Assistant geladene Integrations-Branding sind getrennte Pfade. Nach einem
Iconwechsel deshalb einen vollständigen Release erstellen, HACS neu laden und
den Browser-Frontend-Cache leeren, bevor ein Assetfehler angenommen wird.
