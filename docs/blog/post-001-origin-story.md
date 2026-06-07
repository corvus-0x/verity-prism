# I Investigated a Nonprofit, Submitted My Findings to Federal Regulators, and Then Started Coding

*By Corvus | From Case to Code*

---

About a year ago I found myself buried in public records.

Not metaphorically buried. Literally buried — dozens of PDFs open across multiple monitors, a spreadsheet that had stopped making sense three days ago, and a quiet, accumulating certainty that something significant was hiding in the data in front of me. I was looking into a nonprofit organization that I believed was misusing charitable funds on a significant scale. Property records. Tax filings. Secretary of State documents. UCC financing statements. Court records. More property records.

The truth was in there somewhere. It usually is.

I had no tool designed for this. So I did what you do when the tools don't exist — I started feeding everything I had into Claude and asking questions.

It worked. Slowly, painstakingly, it worked. I submitted my findings to multiple regulatory authorities. That chapter is closed. What it left behind was a question I couldn't stop turning over.

*This should not be this hard.*

---

## The Decision: Build the Tool That Didn't Exist

After the investigation ended I had a choice. Walk away, or figure out what I actually needed and build it.

The tool I needed wasn't a general document storage app. It wasn't a case management system. It wasn't a spreadsheet. It was something specific — a platform that could ingest any document, automatically extract every meaningful data point from it, and then let me search across all of it in plain English. Not "grep for keywords." Plain English. The way I actually think when I'm investigating.

That tool doesn't exist. The closest things are either enterprise software that costs more than most nonprofits' annual budgets, or disconnected pieces that require you to be a developer to wire together.

So I decided to build it.

I kept coming back to one image: a prism. Light goes in as one thing and comes out as everything it was always made of — separated, named, visible. That's what I needed. A document goes in whole — a deed, a tax return, a financing statement — and comes out as every name, every date, every dollar amount, every ID number, each one a separate thing you can hold up and examine. Nothing collapsed back into a summary. Nothing lost in the translation.

I'm building it under the name **Verity Prism**. Verity for truth. Prism for refracting documents into every component they contain.

The fraud investigation use case is the proving ground. But the same problem exists in every industry where documents arrive faster than people can read them — legal, insurance, compliance, real estate. The core platform is the same. The vertical logic sitting on top of it changes.

---

## The Build: What I'm Starting With

 I have an IBM Full Stack Developer certificate. This is the first project where I'm using everything it taught me — and then some.

The stack: **React + Vite** on the frontend. **Python FastAPI** on the backend. **PostgreSQL** as the database — specifically chosen because it has full-text search built in, which means I don't need a separate search service to start. **Claude API** for the extraction and the chat layer. **Docker** from day one so that moving from my laptop to AWS later isn't a rewrite.

The architecture has five layers:
1. Document ingestion — hash first (evidence lock), then store
2. Extraction pipeline — OCR, then Claude identifies the document type, then Claude fills in every field from a schema
3. Knowledge base — PostgreSQL with the extracted fields stored as individual rows, fully indexed
4. Vertical logic — the fraud investigation features sit here, not baked into the core
5. UI — with a plain English search bar as the most prominent element on every screen

I spent the first sessions not writing any code at all. I drew a map first — a design spec, implementation plans, a rough picture of the data model and how the pieces connect. Not rules to follow rigidly, but a direction to move in. Something to come back to when the real decisions start arriving and the path isn't obvious.

---

## What I Learned Before Writing Line One

The investigation taught me something that I think gets missed in most software projects: the data that matters is almost never the data that's easy to get.
 
ProPublica has 990s for nonprofit organizations. But ProPublica only shows you the surface. The IRS TEOS database has the same 990s in XML format — every line, every schedule, every checkbox. The difference between those two sources is the difference between knowing an organization disclosed related-party transactions and knowing exactly which line they checked, what they reported the prior year, and when the disclosures suddenly stopped.

Minute details are what build a case. Software that only gives you the surface doesn't help.

That principle is baked into Verity Prism's architecture at the database level. Every document gets its own extraction schema. A deed produces rows for grantor name, grantee name, consideration amount, parcel number, recording date, preparing attorney, notary name — each one a separate queryable row. A Form 990 produces rows for gross receipts, officer compensation, board independence, conflict of interest policy, related-party disclosures — every governance checkbox that matters.

The platform doesn't summarize. It doesn't decide what matters for you. It breaks documents down to their components and makes every single one visible — because in an investigation, the thing that cracks it open is almost never the thing you expected to be looking for.

---

## What's Next

Task 1: Get Docker running, get FastAPI returning a health check, and make my first commit as Corvus.

---

*From Case to Code is a build journal. I'm documenting the construction of Verity Prism from the first commit to whenever this thing is finished — the decisions, the wrong turns, the architecture that made sense at 2am and still made sense in the morning. Writing for anyone who's ever been buried in documents and felt the specific frustration of knowing the answer is in there somewhere.*

*Follow along: `-corvus` on Hashnode.*
