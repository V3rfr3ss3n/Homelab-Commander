---
title: Contributing and change review
status: active
updated: 2026-10-31
tags: [wiki, maintenance]
---

# Contributing and change review

GitLab leads development through issues and merge requests. GitHub provides the
public source and installation artifacts. Use the existing integration and mirror;
do not build another synchronization layer for a routine change.

Read [AGENTS.md](../../../AGENTS.md), then only the component documents needed for
the task. Preserve existing working-tree changes and use a short-lived feature
branch. A direct change or issue means implement, test, document and deliver an MR;
a question needs an answer without unsolicited edits.

Scale planning to complexity. Delegate only when supported and useful, with
independent files and coordinated shared contracts. Small relevant improvements
can accompany the task; there is no mandatory additional self-optimization pass.

Behavior changes need meaningful regression tests and affected documentation.
Architectural decisions affecting public contracts, persistence, security or
abstraction boundaries need an ADR. Run relevant feedback while iterating, then
complete the required quality and privacy gates before merge. Never auto-merge.

A handoff reports the MR link, actual checks, risks and exact unavailable/failed
commands. A Draft with documented blockers is reviewable work, not a completed
release or green build. See [the full contributing guide](../../../CONTRIBUTING.md).
