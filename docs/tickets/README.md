# Tickets — Verity Prism

The work-order ledger. Every meaningful change starts as a ticket here, written by the **tech-lead** conversation before any code is touched. The ticket is the contract; the PR is the delivery; review checks one against the other.

This is the real-world loop, run solo: **ticket → branch → commits → PR → review → merge.**

---

## Board

| ID | Title | Status | Branch | PR |
|----|-------|--------|--------|----|
| _none yet_ | | | | |

**Status values:** `Open` → `In Progress` → `In Review` → `Merged` (or `Closed` if abandoned).

---

## Definition of Done (global — every ticket inherits this)

A ticket is **not** done until all of these hold. Its own `Definition of done` section adds ticket-specific criteria on top.

- [ ] **Tests pass** — the actual command output is shown at review, not asserted. New behavior has new tests (TDD: failing test first).
- [ ] **Lint clean** — ruff (backend) / ESLint (frontend) pass; no new warnings.
- [ ] **No swallowed errors** — failures surface; no bare `except: pass` or silent fallbacks.
- [ ] **Conventions honored** — thin routers, soft-delete filters, docstrings on services, active hooks green.
- [ ] **Migrations reversible** — if the ticket touches the schema, `downgrade()` is real and tested (incl. enum `DROP TYPE`).
- [ ] **Reviewed** — tech-lead has reviewed against this DoD + the ticket's own, and logged a verdict in the ticket's Review log.
- [ ] **Traceable** — branch is `feat/vp-NNN-<slug>`; commits and PR title reference the ID.

---

## Conventions

**ID scheme:** `VP-NNN`, zero-padded, sequential. Next ID = highest existing + 1.

**Filename:** `VP-NNN-<kebab-title>.md` (e.g. `VP-003-durable-job-table.md`).

**Branch:** `feat/vp-NNN-<slug>` — one branch per ticket, per the project git workflow.

**Traceability (the whole point):** every commit message and the PR title reference the ID:
```
feat: durable job table with worker claim (VP-003)
```
That makes the link bidirectional — the ticket's frontmatter names its branch/PR, and the commits/PR name the ticket. To see a ticket's whole life:
```bash
git log --oneline -- docs/tickets/VP-003*   # the ticket's own history
git log --oneline --grep "VP-003"           # the commits that fulfilled it
```

**Who writes what:**
- The **tech-lead** conversation writes tickets and the Review log. It writes nothing else in the repo.
- The **pair-programmer** conversation writes the code, references the ID in commits, and opens the PR.
- Ticket `status` and the `branch`/`pr` frontmatter get updated as the work moves — by whichever conversation is in normal (non-plan) mode at the time.

---

## Lifecycle

1. **Open** — lead files the ticket during standup. Body is the pasteable work order.
2. **In Progress** — coder starts the branch, sets `status` + `branch`.
3. **In Review** — PR opened, `pr` set. Lead reviews against the Definition of Done.
4. **Merged** — review passed, PR merged. Lead logs the verdict in the Review log.

A ticket bounced back in review goes `In Review → In Progress` with the gap noted — never silently "done."

See `_TEMPLATE.md` for the ticket format.
