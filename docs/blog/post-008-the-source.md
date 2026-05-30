# The Source

*By Corvus | From Case to Code*

---

`sale_amount: $245,000 — 61% confidence`

That's a real field from a real deed. 61% means Claude found a value but wasn't certain. The schema has a threshold; fields below it are flagged. That's the right design. But flagged for what.

The deed was on disk. The extraction was in the database. There was no way to look at both at once. You'd see the field value and either accept it or note the doubt and move on. No way to pull the source document and check the line it came from. The confidence score was a signal pointing at nothing you could reach. The scoring was working. There was just nowhere to go with it.

---

A fraud investigation is built on documents. The investigator reads them, takes notes, builds a timeline. The platform is supposed to do the reading faster and keep better records. But if the extracted fields are the only thing visible and the source documents are invisible, the platform hasn't made the investigator's job easier — it's made it different in a way that's worse. Now the decision is about whether to trust a number, not whether to trust a document.

The distinction matters. A document has context. You can see what's above the line and what's below it. You can see the notary block. You can see if the dollar amount appears twice with different values. The extraction might pick the wrong one. 61% is Claude telling you it might have.

The viewer had to show both.

---

Two panes. PDF on the left, extracted fields on the right. 65% of the space goes to the document — the document is the source. The fields panel scrolls independently. Page navigation at the top. Click a document in the list, the URL updates, the viewer loads.

The PDF renders in-browser via react-pdf, which ships pdf.js internally. No viewer installed, no plugin required, no prompt about whether Adobe is available. The bytes come from the backend through the same authenticated axios client that handles every other API call — the file endpoint is protected by JWT, so you can't fetch a document's raw bytes without being logged in to the workspace that owns it.

The three fetches — document metadata, extracted fields, file blob — run in parallel via `Promise.allSettled`. Not `Promise.all`. If the file fetch fails — the storage volume wasn't mounted, the file was moved — the fields panel still loads. The confidence score is still there. The viewer surfaces a clear message about the missing file and the extracted data isn't lost because the source file isn't reachable. Partial failure is still useful.

---

The `extraction_error` column has been on the Document record since the pipeline was built. When extraction fails, the pipeline writes a reason — up to 500 characters of what went wrong. Until now, that information lived in the database with no surface. The fields panel now shows it: the actual error text, in a monospace box, not just a red banner. If a deed comes through and the conveyance fee calculation breaks, you can read why.

That's the other half of what 61% means. Not just "go check the document." Also: "if extraction failed entirely, here's what it said."

---

80 tests. Two new backend tests cover the file endpoint: upload a document, fetch it via `GET /documents/{id}/file`, assert the bytes match; and a 404 for a nonexistent ID. The extraction pipeline tests are unchanged. The viewer reads what the pipeline produced — it doesn't touch the pipeline.

The next build in this phase is the extraction evaluator: a pass that runs after extraction completes, checks confidence against the schema threshold, and either retries low-confidence fields or escalates to a human review lead. The viewer is the prerequisite for that. An evaluator needs a place for a reviewer to go.

---

*From Case to Code is a build journal. I'm building Verity Prism from scratch and writing down what I'm doing and why. If you've ever been buried in documents knowing the answer was in there somewhere — you know why this exists.*

*Posts 1 through 7 cover the origin, the data model, the extraction pipeline, the agentic chat engine, and the expansion architecture.*

*Follow along: `-corvus` on Hashnode.*
