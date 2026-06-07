# Demo-Readiness Audit

**Date:** 2026-06-04
**Goal:** Make Verity Prism read as *finished* — not 80% — to a recruiter who pulls up the repo or watches a demo. Audit follows the golden path a reviewer actually walks: log in → create workspace → upload → watch extraction → view → search → AI chat.

**Headline:** The code on the golden path is sound. The viewer, pipeline, and error states are genuinely good. What leaks "80%" is the **first-run experience and the front door** — the parts a reviewer hits *before* they ever see the engineering. Fix those first; they're cheap and high-leverage.

---

## How to use this doc

One item at a time. The point is to *understand and retain*, not to clear the list fast.

1. Highlight ONE checkbox below and we work it together.
2. I give the context, the *why*, and the trade-offs.
3. You write the decision-bearing part yourself — the choice should be yours.
4. We verify it actually works.
5. Check it off, confirm it made sense, then move to the next.

Don't batch. A finished, understood item beats three half-grasped ones.

---

## P0 — Demo blockers (a reviewer literally cannot experience the product)

- [x] **No way to log in on a fresh install.** `POST /auth/register` exists in the backend, but there is **no Register page or "Create account" link** in the frontend (`Login.jsx`), and **no seed-user script**. A recruiter who clones, runs `docker-compose up`, and opens `localhost:5173` hits the login screen and is stuck. → Fix: seed a demo user AND put the credentials in the README, *or* add a Register page. (Recommend: both — seed user for the lazy reviewer, register page for completeness.)

- [x] **No sample documents in the repo.** The only examples live in `private/example documents` (gitignored). A reviewer has no deed or 990 to upload, so the "wow" moment — document → structured fields — never fires for them. → Fix: commit 1–2 **non-sensitive** sample docs to a `samples/` folder (synthetic or public-domain — never the real case files).

- [ ] **No screenshot in the README.** Line 9 is literally `<!-- screenshot — add before publishing -->`. For a visual product, a text-only front door wastes the first impression. → Fix: add a hero screenshot or a short GIF of the viewer at the top.

- [ ] **Live extraction needs an Anthropic API key (and spends money).** Even past login with a sample doc, extraction only runs if the reviewer supplies their own key — they won't. → **This is why a deployed demo or a 2-minute recorded walkthrough matters more than "clone and run."** Strategic, not a code fix. Most reviewers will never run it locally; give them something to *watch*.

---

## P1 — "80% feel" on the golden path (polish, credibility)

- [x] **Test counts disagree across docs.** All docs now unified at **222 passing**. (A reviewer who notices contradicts your "I document carefully" story.)

- [x] **Documents page has no empty state.** `DocumentList.jsx` renders nothing when `documents` is `[]`. A fresh workspace shows a dropzone then blank space. → Add "No documents yet — drop a file to begin."

- [x] **"Insurance — Coming soon" is selectable in the New Workspace modal.** Picking it creates a half-defined workspace. → Disable the option (or hide it) for the demo so nobody falls into an unfinished vertical.

- [x] **Verify `.env.example` DATABASE_URL works under docker-compose.** It points at `@localhost:5432`; inside compose the backend reaches Postgres at the `db` service host. Confirm compose overrides it, or the one-command quick-start breaks on a clean clone. *(Verify before asserting.)*

---

## P2 — Off-path, but a curious reviewer might find

- [x] **Demo in a General workspace.** The vertical-aware sidebar already hides Transactions/Findings/Leads for General — so the unfinished fraud cap (signal detection still 🔲) simply never appears. No refactor needed; just the demo path. *(This is your engine/cap separation paying off — worth saying out loud in an interview.)*

- [x] **Sources/connectors is partial** — only IRS TEOS works. Keep it off the demo path or make the others degrade cleanly.

---

## Strengths to protect (don't "fix" these)

- **DocumentViewer** — parallel `Promise.allSettled` fetch, blob-URL lifecycle cleanup, and real error states ("Document not found", "Source file unavailable", pending/failed/no_schema handled). This is the centerpiece and it degrades gracefully. Lead the demo with it.
- **Hybrid semantic search is built but undocumented.** `embedding_service.py` + pgvector are wired into search, yet the README stack table doesn't mention it. This is the *opposite* of a defect — you built something impressive and are hiding it. → Surface it in the README.
- **Engine/cap separation** makes "demo General, hide the unfinished caps" a one-line decision instead of surgery.

---

## Recommended order of attack

1. Seed demo user + README credentials  (unblocks login)
2. Commit sample documents  (unblocks the wow moment)
3. Deploy a demo *or* record a 2-min walkthrough  (the thing most reviewers actually consume)
4. README screenshot + unify test count + surface hybrid search  (front-door credibility)
5. Empty state + disable "Insurance" option  (polish)
