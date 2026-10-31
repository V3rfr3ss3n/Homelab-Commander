# Contributing

Thank you for helping build Homelab Commander. The project is designed for public
collaboration and treats maintainability, privacy, and predictable Home Assistant
behavior as product features.

## Before starting

1. Read [AGENTS.md](AGENTS.md), then use the [documentation index](docs/README.md)
   to load only the context relevant to your task.
2. Check the [current TODO](docs/00-project/todo.md) or
   [backlog](docs/00-project/backlog.md) when selecting work.
3. Read the relevant ADRs for architecture changes and security documentation for
   changes to trust boundaries. See the [workflow](docs/03-development/workflow.md).

## Local feedback

Use `make quality-fast` for existing static/documentation checks and
`uv run pytest <test-path> --no-cov` for focused regression tests. Neither replaces
`make quality`, the independent CI validators, or `make release-check` for releases.

## Merge requests and pull requests

GitLab is the development source; use the existing configured remote and access.
GitHub distributes the public source and installation artifacts. Do not configure
another mirror, publish documentation or change visibility as part of a routine MR.

A pull request should be narrowly scoped, explain the user impact, include tests,
and update relevant documentation. It must pass the quality gate documented in
[docs/03-development/quality-gates.md](docs/03-development/quality-gates.md).

Do not include screenshots, logs, fixtures, or configuration copied from a real
Home Assistant or homelab environment. Replace all deployment values with generic
examples before committing.

## Commit style

Use short imperative subjects. Conventional Commit prefixes are preferred:
`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `build:`, and `chore:`.

By contributing, you agree that your contribution is licensed under the MIT
license used by this repository.
