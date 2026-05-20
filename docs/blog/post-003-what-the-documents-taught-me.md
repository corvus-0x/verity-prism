# What the Documents Taught Me

*By Corvus | From Case to Code*

---

One transaction didn't make sense for weeks. An elderly couple sold two properties to a nonprofit well below appraised value. Every signal said acquisition of vulnerable parties — a pattern worth flagging. I had the deeds, the parcel records, the numbers. I had no explanation.

Then I read an obituary.

The survivors list named the sellers as family members of the nonprofit's founding family. The discounted sale wasn't predatory. It was internal. The same month, the nonprofit conveyed a separate property to those same individuals at no cost. Both legs of the exchange happened simultaneously. Neither disclosed on the related-party schedules of the annual tax filing.

I'd been reading the transaction as a financial event. It was a family event dressed as a market sale.

---

I almost didn't build a schema for obituaries.

The IDP platform has a list of document types — deed, 990, UCC, SOS filing, building permit — and obituary wasn't on it. It felt like background, not evidence. Something you'd read for context, not extract fields from.

That was the wrong model.

The extraction schemas I'd been designing were based on what seemed obvious. The fields a deed has. The schedules a 990 contains. What I found when I actually read the documents — 21 parcel records, 7 deeds, 9 IRS filings, 10 SOS filings, 22 UCCs, a permit spreadsheet, 10 audit reports — is that every document type taught me something the templates didn't contain.

The parcel records, read in sequence, showed a demolition pattern no template would have anticipated. The same entity would acquire a property, wait one assessment cycle, and the improvement value would collapse to zero. The land stayed. This happened across four properties. The building permit records confirmed the construction activity: millions in permitted work at a single address, same contractor across seven years. The parcel records on adjacent properties showed the structures gone.

The schema needed a field for that. `improvement_demolished: boolean`. Fires when current improvements equal zero and any prior year in the valuation history shows improvements above $50,000. That field doesn't appear in any county auditor documentation. It exists because I read the documents.

---

The UCC filings were the other lesson. I went in looking for a specific signal — multiple amendments to the same financing statement filed within minutes. I found it: five amendments in twelve minutes and twenty-nine seconds, all adding family members as co-debtors to an agricultural lien. The UCC schema needed `filing_time` at second precision. Not minute. Second. Because the signal is twelve minutes, not an estimate.

What I didn't expect: buried in the same document set were originals from years earlier that named the nonprofit's president as a personal agricultural debtor — at the same address listed as the nonprofit's principal office on the annual tax return. The nonprofit is registered at the family farm. The president carries agricultural debt at that address.

That's not a field in any UCC schema template. It's a connection that only surfaces when you cross the UCC against the 990 against the parcel records. The extraction schema captures both so the search layer can find both.

---

The obituary schema has fields for children, spouses, siblings, and in-laws — with locations — because the network is how transactions move between entities. One obituary explained a property exchange that three weeks of document analysis hadn't. The mechanism wasn't financial. It was genealogical.

A template would have given me: deceased name, birth date, death date, survivors. A schema built from an actual document gives you a family tree that explains why a transaction looked like exploitation and was actually inheritance.

---

Eleven schemas. 370 fields in the parcel record alone. That number sounds like over-engineering until you understand what it contains: eight sales per property, fourteen tax payments, six years of valuation history, a lender ID field that appears on every property connected to the investigation and almost nowhere else. That field is a single value in the county auditor's record. Cross it across a workspace and every connected property surfaces at once.

The database doesn't surface that pattern by itself. But when you ask it to find all documents where that ID appears across a workspace, it answers in milliseconds. That's the difference between having the data and being able to work with it.

---

The pipeline is built. Upload a document — any of these eleven types — and it returns immediately with `status: pending`. Everything else runs after the response is sent. OCR, type detection, schema lookup, field extraction, FTS index update. If a document type has no schema, the status becomes `no_schema` and an investigation lead appears in the workspace: this document needs a schema before fields can be extracted.

Structured XML files bypass OCR entirely. The source already contains known element paths. Extraction confidence is 1.0 because there's no interpretation — just parsing.

Twenty-nine tests. All green.

That's the session. NLP search is next — turning "find all properties where the acquiring entity paid more than twice the appraised value" into a query that actually runs.

---

*From Case to Code is a build journal. I'm building Verity Prism from scratch and writing down what I'm doing and why. If you've ever been buried in documents knowing the answer was in there somewhere — you know why this exists.*

*Follow along: `-corvus` on Hashnode.*
