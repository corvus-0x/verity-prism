# The Database Is the Investigation

*By Corvus | From Case to Code*

---

The first version of this broke on the data model. Not the code — the foundation. A deed would go in and come out as one row, everything flattened into a JSON column that felt complete until the moment I needed to ask a question it hadn't anticipated.

I needed to pull every grantor tied to a specific LLC across four years. Couldn't do it. The data was there. The structure wouldn't let me get to it.

That's when I stopped and rebuilt.

Catalyst was the first attempt. The idea was right — pull documents in, extract the important stuff, build investigation tools on top. What wasn't right was how I stored what I pulled. A deed isn't a single thing. It's a grantor, a grantee, a dollar amount, a parcel number, a recording date, the attorney who prepared it, the notary who signed off. I was storing all of that as one record. Eleven facts collapsed into a blob that looked like data but didn't behave like it.

Building on top of that was like trying to run queries on a filing cabinet. The friction wasn't in the code. It was baked into the foundation before I wrote a single view.

So I rebuilt the schema. Made a different call about how fields get stored.

One row per field, per document. A deed with eleven fields gives you eleven rows. A 990 gives you rows for gross receipts, officer compensation, related-party disclosures, board independence checkboxes — every piece individually addressable, sitting there waiting to be pulled. That's `document_extractions`. More to set up. Worth it.

The question I kept coming back to was simple: do I trust a JSON blob to hold everything a deed contains in a way I can query six months from now, looking for something I don't know I need yet? I didn't. So I didn't use one.

The fraud vertical is what makes this non-negotiable. Fraud signals don't announce themselves. You're not looking for a smoking gun — you're looking for a grantor name that shows up in three transactions across four years, connected to an entity that shares an address with a nonprofit that stopped filing. That query only works if every grantor name, every address, every date is its own row.

"Find documents that mention this name" is not the same as "show me every transaction where this person appears as grantor, sorted by date, tied to this workspace." First one is search. Second one is an investigation.

In the real case that built this — the one that ended with a formal referral to the state Attorney General — the detail that broke it open wasn't in any summary. It was one field in one schedule in one year's 990 that directly contradicted what was filed the year before. One row. If that had been collapsed into a blob it would have stayed invisible.

The schema exists so that can't happen.

Foundation work this session. Workspaces, users, entities, findings — in and out of the database without losing anything. No extraction pipeline yet, no AI layer, nothing a user would ever touch.

Sixteen tests. All green.

That's the session. Extraction pipeline is next — that's when it gets interesting.

---

*From Case to Code is a build journal. I'm building Verity Prism from scratch and writing down what I'm doing and why. If you've ever been buried in documents knowing the answer was in there somewhere — you know why this exists.*

*Follow along: `-corvus` on Hashnode.*
