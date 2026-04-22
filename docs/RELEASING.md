# Releasing — SDK and Cross-Repo Version Policy

The `intuno-sdk` is the pivot point of the Intuno ecosystem. It sits
between the `wisdom` backend and every client (`samantha-foundation`,
`wisdom-agents`, user apps), so its release cadence drives everyone
else's.

This document is the single source of truth for *when* to cut a release
and *how* dependent repos consume it.

## SemVer rules

We follow [Semantic Versioning](https://semver.org/):

| Bump | When |
|------|------|
| **MAJOR** (1.0.0 → 2.0.0) | Any breaking change to a public method signature, removed method, or renamed kwarg. Also when a required backend contract changes in an incompatible way. |
| **MINOR** (0.3.0 → 0.4.0) | New public methods, new MCP tools, new integration helpers, new optional kwargs with sensible defaults. |
| **PATCH** (0.4.0 → 0.4.1) | Bug fixes, docstring/README changes, CHANGELOG backfills, CI-only changes. No behavior change for existing callers. |

We remain under 1.0.0 while the API is considered provisional.

## Release workflow

1. **PR with `CHANGELOG.md` entry.** Every release-worthy PR adds a
   section to `CHANGELOG.md` under the next target version. Enforced
   in code review — no exceptions except trivial docs PRs (typo
   fixes).
2. **Version bump in `pyproject.toml`.** Same PR or an immediate
   follow-up. Don't let main diverge from the published version for
   long.
3. **Tag and publish.**
   ```bash
   git tag v0.4.0 && git push origin v0.4.0
   # CI (Publish workflow) pushes to PyPI.
   ```
4. **Bump downstream pins.** Open PRs in `samantha-foundation` and
   `wisdom-agents` to update `intuno-sdk` version constraint (see
   below).

## Downstream dependency pinning

| Repo | How it pins | When to bump |
|------|-------------|--------------|
| `samantha-foundation` | `intuno-sdk>=0.X,<0.(X+1)` in `pyproject.toml` | On every SDK MINOR. PATCH is automatic via range. |
| `wisdom-agents` | `intuno-sdk>=0.X,<0.(X+1)` in `pyproject.toml` | Same as above. (Previously pinned to local path — fixed in `wisdom-agents#65`.) |
| `wisdom` (backend) | No Python dep on SDK. | Track API compatibility via contract tests. |

**Rule:** dependent repos pin to a compatible-release range (`>=X.Y,<X.(Y+1)`)
so PATCH bumps flow automatically but MINOR bumps require a deliberate
update.

## Backend coordination

Because the SDK calls backend routes, backend-breaking changes and SDK
changes need to land close in time. The coordination protocol:

1. **Backend-first for additive changes.** New routes ship in `wisdom`
   before SDK clients call them. The SDK release can wait a week.
2. **Contract tests in `intuno-sdk/tests/`.** Mocked via `respx`.
   These tests pin the expected request/response shape — if the
   backend changes them, the SDK test fails first.
3. **Never remove a backend route without deprecating for one SDK
   minor.** Deprecate in release *N*, remove in *N+1*.

## The "cross-repo tagging" question

We do **not** do synchronized tags across repos (e.g., "everyone cuts
v0.4.0 together"). Each repo has its own version.

Reason: `wisdom`, `wisdom-agents`, `samantha-foundation`, and
`intuno-sdk` evolve at different cadences and serve different audiences.
Synchronized tags would force unnecessary bumps or block fast-moving
repos on slow-moving ones.

Dependency pinning (above) is the coordination mechanism instead.

## Release notes

`CHANGELOG.md` entries are the release notes. GitHub releases copy the
latest section verbatim — keep them scannable:

- Group by **Added / Changed / Fixed / Removed / Security**.
- Lead each bullet with the concrete public name (method, tool, file).
- Link to tutorials / docs when a new feature has dedicated coverage.
- One line per bullet; keep paragraphs out of the changelog.
