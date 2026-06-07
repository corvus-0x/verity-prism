# The Rate

*By Corvus | From Case to Code*

---

The automation rate came back at 48%.

I've had tests passing for months — the pipeline runs, the extractions land, the confidence scores come back in range. But this was the first time I pointed the engine at a real investigation: 23 documents from a case I assembled by hand before any of this existed. Deeds, 990 filings, SOS records, parcel records, building permits — the same documents I'd been pulling from county recorder portals and the IRS TEOS database by hand before I decided to build something systematic.

Eleven complete. Twelve routed to the review queue.

---

I traced the 12. Most of them had extracted correctly — confidence scores reasonable, field values matching what was in the documents. But each one had fields below the 0.75 threshold, and the evaluator flags any document with low-confidence fields for human review.

The fields below threshold weren't bad extractions. They were absent fields.

The PARCEL-RECORD schema has 370 definitions. A parcel record for a rural nonprofit might have 120 of them. The other 250 don't exist in that document — no subdivision name, no improvement schedule, no agricultural exemption code.

Claude returns them at roughly 0.1 confidence, which is its way of saying: I looked, and there's nothing here.

The evaluator runs the same check on absent fields and extracted fields alike — confidence below 0.75, document goes to review, regardless of why the confidence is low or whether there was ever a value to find.

The reviewer opens the first document in the queue. The flagged field is labeled subdivision name. They scan the parcel record — top to bottom, then again — looking for it. It's not there. Not anywhere in the document. The field wasn't there and wasn't going to be there. They've been sent to fix something that isn't broken.

---

This is the thing I had missed: absence and uncertainty are not the same problem.

Low confidence on an extracted field means the machine saw something, tried to read it, and wasn't sure. The reviewer can look at the source document, confirm the value, and move on. That's the loop the confidence threshold is designed to close.

Absent fields don't have that loop. There's no value to confirm because there's no value. The document doesn't have a subdivision name for the same reason your personal tax return doesn't have a line for farm equipment depreciation — it just doesn't apply. Asking someone to verify that is wasted time at best. At worst, it erodes trust in the queue itself — and a reviewer who stops trusting the queue starts skimming.

That distinction matters more on an investigation platform than anywhere else. Every hour a reviewer spends on a false flag is an hour they're not spending on documents that actually need attention. And if the queue trains people to assume it's noisy, they stop reading carefully. That's when real issues get through.

---

An absent field isn't a confidence problem — it's the shape of that specific document against that schema. The fix is a single check before the evaluation loop: if the field has no value, skip it.

A tax-exempt nonprofit's parcel record has no agricultural exemption entry because there's nothing to exempt — not because extraction failed, but because the field just doesn't apply. Routing that to human review is asking a reviewer to verify the absence of something the document never claimed to have.

After the fix: 13 complete, 10 in review. 57%.

The 10 still in review have real issues. Some are property record screenshots that got classified as SCREENSHOT and evaluated against a schema built for social media — the schema has fields for likes counts and comment authors that a county auditor grab doesn't contain. Some are deeds with complex legal descriptions where the extraction was genuinely uncertain. The evaluator is doing its job on all of them.

---

57% is still below the 70% industry benchmark, but it's the real number now — what the engine actually does against real documents from a real investigation without any configuration tuned to that case.

The 48% figure included documents the engine had correctly processed. The problem was in what counted as a problem. The absent-field check didn't fix the engine — it fixed what the engine was measuring.

Three things on the list next: currency normalization, the SCREENSHOT schema mismatch, and whether the baseline moves with either of them.

The baseline is honest now.

---

*From Case to Code is a build journal. I'm building Verity Prism from scratch and writing down what I'm doing and why. If you've ever been buried in documents knowing the answer was in there somewhere — you know why this exists.*

*Posts 1 through 11 cover the origin, the data model, the extraction pipeline, the agentic chat engine, the expansion architecture, the UI layer, the audit, and the review pane.*

*Follow along: `-corvus` on Hashnode.*
