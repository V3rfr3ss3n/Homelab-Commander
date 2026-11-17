---
title: UI guidelines and semantic tokens
status: proposed
updated: 2026-11-16
tags: [design, accessibility, localization]
---

# UI guidelines

Preserve the existing navy surfaces, teal actions and restrained borders. Content
is compact, with room between actions and explicit labels. Use the existing inline
SVG icon vocabulary with text; icon-only controls require an accessible name and
focus outline. Do not use success color for unknown, failed or unsupported state.
Outcome, review attention and authorization are distinct concepts.

## Implemented token aliases

Tokens are in [ui.css](../../backend/homelab_backend/frontend/ui.css). Legacy palette
names remain compatible while new components consume semantic aliases.

| Role | Tokens / current values |
| --- | --- |
| Surface | `--surface-page` → `--bg`, `--surface-panel` → `--card` |
| Text/border | `--text-primary`, `--text-secondary`, `--border-default` |
| Feedback | `--status-success`, `--status-error`, `--status-warning`, `--status-info` |
| Focus | `--focus-ring`, 2px outline and 3px offset |
| Spacing | `--space-1` … `--space-5`: 4, 8, 12, 16, 24px |
| Shape | `--radius-control`: 8px; `--radius-panel`: 14px |
| Type | `--font-caption`: 12px; `--font-body`: 15px; inherit system font |
| Controls | `--control-height`: 36px in compact resource header |

CSS custom properties cannot directly supply media-query conditions. The resource
panel stacks above its table at 900px; legacy shell uses 750px and 1100px. Keep these
explicit until the independently reviewed shell slice consolidates breakpoints.
Resource tables scroll horizontally inside their own labeled region at narrow
widths; the document must not scroll sideways. No external fonts or icon service.

## Interaction/accessibility contract

Use real buttons, links, tables, labeled form controls and native dialogs. Sort
headers expose `aria-sort`; select-page exposes checked/mixed state; status changes
use a polite status region. Failed inventory stays visibly stale and cannot be
selected until a successful retry. Errors use the existing safe diagnostics.
Focus moves to an editor name or details heading on explicit opening and returns
to the triggering control on close. Escape dismisses the manager dialog. Native
checkboxes work with Space; search submits with Enter. Avoid custom grid keyboard
semantics until they have a separately tested need. Reduced-motion preferences
are respected. Color always has a text/status/selection counterpart.

WCAG 2.2 AA remains a validation target, not a compliance certification. Tests cover
keyboard focus, labels, mobile overflow and both hosting modes; a complete assistive
technology/contrast audit is still a separate acceptance exercise.

## English and later localization (#70)

Management UI copy remains English. No language switch or translation framework is
added. Existing browser-locale date/number formatting remains compatible; HA's
existing translation catalogs are independent and are not removed or expanded.
Do not mistake English UI copy for a completed localization system.

Before shipping another management-UI language, #70 must deliver extracted catalogs,
complete UI/validation/error/accessibility coverage, locale selection/persistence,
plural rules, date/number formats, fallback behavior, automated missing-key checks,
and browser tests for every supported locale. No partial language may ship.

No permanent onboarding prompts or repeated tips. Help is contextual (for example,
collapsed smart-rule syntax), while existing Host setup stays a deliberate dialog.
