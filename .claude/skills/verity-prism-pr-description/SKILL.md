---
name: verity-prism-pr-description
description: Use when creating a pull request for a Verity Prism implementation phase branch — reads the phase spec and audit doc to produce a complete, accurate PR description rather than guessing context from memory.
---

# Verity Prism — Phase PR Description

## Overview
Generates PR descriptions for `feat/phase-N-*` branches by reading primary sources: the approved spec, the audit findings, and the live commit list. Avoids guessing finding descriptions or test counts.

## Process

Run these in order before writing a single word of the PR body:

- [ ] **Read the spec:** `docs/superpowers/specs/<date>-phase<N>-*-design.md` — pull the exact findings in scope, decisions made, what was deferred.
- [ ] **Read the audit doc:** `docs/code-audit-2026-05-29.md` — pull the finding severity, one-line description, and the exact "Fix" instruction for each finding being closed.
- [ ] **Get commit list:** `git log main..HEAD --oneline`
- [ ] **Get test delta:** `docker-compose run --rm -e TEST_DATABASE_URL=... -e SECRET_KEY=... backend pytest tests/ 2>&1 | tail -1` — note the before/after count (check prior PR for the "before" number).
- [ ] **Check for migrations:** `git diff main...HEAD --name-only | grep alembic/versions` — if any, note what DDL they install and that `alembic upgrade head` is required on deploy.

## PR Description Template

```markdown
## Summary

- **<FINDING-ID>** — <one-line from audit doc, finding severity in parens>. <what was done, 1 sentence>.
[repeat for each finding]

## Migration notes (if any)

Migration `<revision_id>` — <what DDL it installs>. Requires `alembic upgrade head` on deploy before starting the app.

## Test delta

<N_before> → <N_after> tests (+<delta> new). All passing.

New test files: `<list any created test files>`

## Findings closed

| Finding | Severity | Description |
|---|---|---|
| <ID> | <Critical/High/Medium/Low> | <exact description from audit doc> |
[repeat]

## Test plan

- [ ] Full suite: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test -e SECRET_KEY=<strong-key> backend pytest tests/ -v` → <N> passed
- [ ] <one specific verification per finding, e.g. "UPDATE audit_log raises InternalError">
- [ ] Ruff lint clean: `ruff check backend/app/ backend/tests/`

🤖 Generated with [Claude Code](https://claude.ai/claude-code)
```

## Quick reference

| What to include | Where to get it |
|---|---|
| Finding IDs + severity | `docs/code-audit-2026-05-29.md` |
| Decisions / deferred scope | Phase spec file |
| Commit list | `git log main..HEAD --oneline` |
| Test count | Run the suite; check prior PR for baseline |
| Migration revision ID | `git diff main...HEAD --name-only \| grep alembic` |
| Deferred items | Spec "out of scope" section |

## Common mistakes

**Writing from memory** — Finding descriptions drift from the audit doc's exact language. Always copy from the source.

**Omitting migration impact** — Any phase that adds an Alembic revision requires an `alembic upgrade head` note. The app will error on next deploy if skipped.

**Wrong test count** — Use the actual suite output. The baseline count is in the previous phase's PR, not in your head.

**Missing deferred scope** — The spec lists what was intentionally left out. Including this in the PR prevents reviewers from filing "why didn't you also fix X?" comments.
