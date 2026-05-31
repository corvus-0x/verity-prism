# The Queue

*By Corvus | From Case to Code*

---

The review queue shows you the fields that extracted with low confidence. It doesn't show you the fields that didn't extract at all.

`ExtractionTable.jsx` maps over `extractions` — the rows in the database. If a batch fails and a field never gets a row, it isn't in the table. The document routes to the review queue because the confidence evaluator flagged something. The reviewer opens it, sees the flagged fields, corrects them, saves. The document clears.

The fields that were never extracted stay missing. There's no row to flag. Nothing to correct. The table has no way to surface what it never received.

---

The confidence threshold is supposed to close a loop. A document below threshold routes to review. A human verifies the extraction, corrects what's wrong, signs off on the record. The machine runs, the human confirms, the result is trustworthy.

That loop has an assumption in it: the machine always returns something, even if it's wrong. Low confidence on a grantor name means Claude extracted a value it wasn't sure about. The reviewer looks at the deed and corrects it. The record gets the right value. The loop closes.

What happens when the batch errors and Claude returns nothing?

The evaluator runs over an empty list. No low-confidence fields — because there are no fields. Nothing routes to review on that basis. But even if the document gets flagged for another reason and the reviewer opens it, they see a table built from the extractions database. The empty fields don't exist in the database. They aren't in the table. There's no row to edit, no indicator that something is supposed to be there, nothing.

The schema knows `grantor_vesting` belongs in a deed. The review pane doesn't know that. It shows what was extracted. The investigator sees a table of successful extractions and has no way to know what the schema expected that they're not seeing.

---

This is the part that mattered because I'm the investigator this platform is built for.

A document in the review queue means something needs attention. A reviewer opens it expecting to see the problem and fix it. If the problem is a missing field — never extracted, no row in the database — the review pane has nothing to show them. The queue put them in the room. There's nothing in the room.

Telling an investigator an extraction failed without giving them a way to fix it is as bad as not telling them at all. Worse, maybe. A silent failure at least doesn't interrupt the workflow. A visible failure that routes nowhere erodes the trust that the system is worth using.

---

The confidence threshold is only half the system.

The other half is a review pane that maps over `schema.schema_fields` — every field the schema defines — not over the extractions table. Fields with extraction rows get pre-filled. Fields without rows get empty editable inputs. The reviewer reads the PDF on the left. They see what the schema expects on the right. They fill in what's missing. Same action whether the field extracted with low confidence or didn't extract at all.

The backend write path is mostly there. Human corrections go in as `attempt=3` — the pipeline writes attempts 1 and 2, corrections write 3. But the current path patches an existing extraction row. A missing field has no row to patch. It needs an insert endpoint: a new `attempt=3` record created from nothing, not derived from a prior extraction.

One endpoint. The pane change on the frontend. Then the threshold actually does what it says — it routes to review, and review gives the investigator something to do about it.

---

160 tests passing. Phase 2E merged. The full review pane lands before the fraud vertical goes on — signals run against extracted fields, and a field that's missing without anyone knowing produces a false negative on signal detection.

The queue was routing. There was nowhere to go.

---

*From Case to Code is a build journal. I'm building Verity Prism from scratch and writing down what I'm doing and why. If you've ever been buried in documents knowing the answer was in there somewhere — you know why this exists.*

*Posts 1 through 10 cover the origin, the data model, the extraction pipeline, the agentic chat engine, the expansion architecture, the UI layer, and the audit.*

*Follow along: `-corvus` on Hashnode.*
