---
name: tech-lead
description: Use when the tech-lead/boss conversation files a TICKET (work order) for the pair-programmer conversation to implement. Triggers — "/tech-lead", "write the ticket", "work order", "hand this off". The full boss persona lives in the `tech-lead` OUTPUT STYLE (switch with /output-style); tickets live in `docs/tickets/`. This skill is the quick pointer to both.
---

The tech-lead **persona** lives in the `tech-lead` output style (`.claude/output-styles/tech-lead.md`) — switch with `/output-style`. Tickets (the persisted work orders) live in **`docs/tickets/`**.

To file a ticket:
1. Read `docs/tickets/README.md` for the board, `VP-NNN` ID scheme, and lifecycle.
2. Copy `docs/tickets/_TEMPLATE.md` → `docs/tickets/VP-NNN-<kebab-title>.md`, fill it in, `status: Open`.
3. Add a row to the board table in `docs/tickets/README.md`.
4. Give Tyler the ticket body to paste into the pair-programmer conversation.

The lead writes tickets and the Review log — nothing else in the repo. Branch is `feat/vp-NNN-<slug>`; commits and PR title reference the ID for traceability.
