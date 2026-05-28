# Fixes & Improvements — Portfolio Hardening

Private working list (gitignored). Based on a recruiter / hiring-engineer read of the repo.

---

## Priority 1 — Highest ROI, do first

### 1. Rewrite the README (it undersells the project)
- Current README says *"Planning phase complete. Build in progress. Implementation begins now."*
- Reality: ~7,200 lines of Python, 75 passing tests, 5 migrations, working extraction pipeline + agentic AI layer.
- A skimmer reads the current line and assumes vaporware / not started.
- **Action:** rewrite to show what actually works. Lead with a screenshot or a 30-second demo GIF. List real, working features.

### 2. Add CI (no `.github/workflows/` exists)
- 75 tests exist but nothing runs them automatically — biggest "hasn't worked on a team" signal.
- **Action:** add a GitHub Actions workflow that runs:
  - `pytest` (backend, in Docker for DB access)
  - frontend tests
  - a linter (see #3)

### 3. Add linting / formatting / type-checking config
- No ruff/black/mypy (backend) or eslint/prettier (frontend) config visible.
- **Action:** add `ruff` + `black` + `mypy` for Python, `eslint` + `prettier` for the frontend. Wire into CI from #2.

---

## Priority 2 — Credibility

### 4. Deploy something live (or drop the AWS claim)
- README claims AWS infra; repo is local docker-compose only.
- **Action:** either deploy a live instance (Fly / Railway / ECS) and link it, or remove the AWS claim. A live URL beats everything else.

### 5. Build out the frontend
- 1,400 lines of frontend vs 7,200 backend.
- README headlines "plain English search bar as the primary interface," but the UI is the least-developed part.
- **Action:** make the search experience demoable end-to-end.

### 6. Use PRs even when solo
- 50 commits, single contributor, no PRs — zero collaboration signal.
- **Action:** do future work via feature branches + PRs to show you know the workflow.

---

## Priority 3 — Polish

- Move `SECRET_KEY: dev-secret-key-change-in-production` out of `docker-compose.yml` into env / `.env` (even for dev).
- Review pinned dependency versions (e.g. `bcrypt==3.2.2` is old).
- Be ready to verbally defend every architecture decision in an interview:
  - Why hash-first as the evidence lock.
  - Why the audit log is a DB trigger, not app code.
  - Why extraction is schema/DB-driven instead of code-driven.
  - Why the AI chat uses a native tool-use loop with `workspace_id` injected by the dispatcher.

---

## What's already strong (keep / lean on these)
- Clean layering: thin routers → services → models/schemas.
- Fail-fast pipeline with status + error capture at each step; background processing with its own DB session.
- 75 tests including agentic-loop mechanics, TDD discipline.
- Documented design decisions (specs, plans, roadmap).
- Good commit hygiene (`feat:/fix:/docs:/test:`).
- Immutable audit log, soft deletes, engine-vs-vertical separation.
