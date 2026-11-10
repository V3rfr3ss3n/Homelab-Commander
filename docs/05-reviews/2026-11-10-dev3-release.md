---
title: 0.3.0-dev.3 development release evidence
status: review
date: 2026-11-10
tags: [review, release, validation]
---

# 0.3.0-dev.3 development release evidence

## Scope and authorization

The owner explicitly requested merging the pending feature branches and publishing
an updateable development release. MRs !26, !27 and !28 were merged in dependency
order using their reviewed source SHAs and successful source pipelines. A release
metadata MR aligns Python, integration, App, Docker/Compose and workflow versions.
Compatibility identifiers, authentication and `/api/v1` remain unchanged.

## Automated preparation evidence

`UV_NO_SYNC=1 make release-check` passed: 367 tests, independent 98.43% line and
95.89% branch coverage, formatting/lint/strict types/docs/audit/privacy and release
metadata checks. Initial version-pin assertions still expected dev.2; they were
updated to dev.3 before the full successful rerun, without weakening any gate.
The wheel version and packaged source/UI files match the candidate exactly.

A public dev.2 image was pulled without registry credentials. Its isolated,
network-disabled container seeded synthetic inventory, disabled task/assignment,
terminal failed job/log, preferences and locally generated SSH identity. Installing
the exact dev.3 wheel on that runtime and starting against the same data verified
migration 6 to 7, stable IDs/data, assignment/preference state, identical private/
public key and known_hosts bytes, key permissions and PID 1 UID 10001. Authenticated
UI login/read/review worked without executing any host action. No real target or
infrastructure was contacted; registry access was only for the public artifact.

## Publication gates and limits

Exact merged-revision Quality/HACS/Hassfest/CodeQL/secret and native multi-arch
container gates must pass before version tagging/publication. The public-image
manifest/anonymous runtime gate and a second isolated upgrade using the actual
published dev.3 image are recorded in the release run and notes, not presumed here.
No package visibility or persistent credentials are changed by release preparation.
A full fresh HA OS/Supervisor installation walkthrough remains manual acceptance;
this development candidate does not claim that production-install milestone.
No automatic rollback or new backup mechanism is introduced. Older binaries may
not understand saved icon overrides; normal backup/recovery guidance still applies.
