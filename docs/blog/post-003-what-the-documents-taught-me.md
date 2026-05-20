# What the Documents Taught Me

*By Corvus | From Case to Code*

---

The Albers transaction didn't make sense for three weeks. An elderly couple sold two Darke County properties to a nonprofit for $67,000. Combined appraised value: $197,870. Thirty-four cents on the dollar. Every pattern I'd built said this was predatory — a nonprofit acquiring from vulnerable people below market. I had the deed, the parcel records, the transaction flagged as anomalous. I had no explanation.

Then I read an obituary.

Lester J. Homan died September 27, 2023. In the survivors list: five children, sixteen grandchildren, and among the siblings and in-laws — Diana and Don Albers of Osgood. The Albers who sold the properties weren't strangers. They were family. The $67,000 wasn't market rate because it wasn't a market transaction. The same month, the nonprofit gave the Albers a Mercer County lot for free. Both legs of the exchange happened the same day. Neither transaction disclosed it on Schedule L.

I'd been trying to understand the transaction as a financial event. It was a family event.

---

The reason I'm writing this is that I almost didn't build a schema for obituaries. The IDP platform has a list of document types — deed, 990, UCC, SOS filing, building permit — and obituary wasn't on it. It felt like background material, not evidence. Something you'd read for context, not extract fields from.

That was the wrong model.

The extraction schemas I'd been designing were based on what seemed obvious. The fields a deed has. The schedules a 990 contains. What I found when I actually read the documents — 21 parcel records, 7 deeds, 9 IRS filings, 10 SOS filings, 22 UCCs, a permit spreadsheet, 10 audit reports — is that every document type taught me something the schema templates didn't contain.

The parcel records, read in sequence, showed a demolition pattern no template would have anticipated. Buy the property. Wait one assessment cycle. The improvement value collapses to zero. The land stays. This happened on four properties. The building permit records confirmed it: Do Good pulled $6 million in construction permits for 25 W. Main. The restaurant. The restrooms. The visitor center. Every permit to the same contractor — Baumer Construction — over seven years. The parcel records across the street showed the structures gone.

The schema needed a field for that. `improvement_demolished: boolean`. Computed during extraction. Fires when current improvements equal zero and any prior year in the valuation history shows improvements above $50,000.

That field doesn't exist in any county auditor documentation. It exists because I read the documents.

---

The UCC filings were the other lesson. I went in looking for the SR-004 signal — multiple amendments to the same financing statement filed within minutes. I found it: five amendments in twelve minutes and twenty-nine seconds on August 2, 2022, all adding Homan family members as debtors to a Farm Credit agricultural lien. The UCC schema needed a `filing_time` field at second precision. Not minute precision. Second precision. Because the signal is twelve minutes, not an estimate.

What I didn't expect: two of the originals in the document set were filings from 2015 that named Karen Homan — the nonprofit's president — as a personal agricultural debtor. At 6712 Olding Road, Maria Stein. The same address she lists as the nonprofit's principal office on the 990. The nonprofit is registered at the Homan family farm. She was carrying Farm Credit agricultural debt at that address three years before Do Good was incorporated.

That's not a field in any UCC schema template. It's a connection that only surfaces when you cross the UCC against the 990 against the parcel records. The extraction schema needs to capture both so the search layer can find both.

---

The obituary schema has twenty-two fields for children and siblings because rural Ohio farming families are large and the network is how the fraud moves. One obituary gave me: Karen Homan is Jay's wife (Lester's son). The fire company secretary Greg Homan is Lester's son (Karen's brother-in-law). The Albers are Lester's family. Tara Partington — Lester's daughter — lives in Maria Stein, which is the geographic hub of the network.

A template would have given me: deceased name, birth date, death date, survivors. A template built from an actual document gives you a family tree that explains why an elderly couple sold property at thirty-four cents on the dollar.

---

Eleven schemas. 370 fields in the parcel record alone. That number sounds like over-engineering until you see what it contains: eight sales per property, fourteen tax payments, six years of valuation history, the lender ID field that appears on every Do Good property and nowhere else in the county. That lender ID — 937 — appears on the restaurant, the veterans center, the vacant lots, the residential houses, the subdivision lots, the Mercer County parcels. Farm Credit Mid-America PCA has a Celina Ohio branch. Brenda Mescher (Farm Credit employee) filed UCC amendments for the Homan family. Karen Homan is personally on their agricultural loans.

Lender ID 937 is a single field. It connects everything.

The database doesn't know that yet. But when I ask it to find all documents where `lender_id = 937` across a workspace, it will find all of them instantly. That's the difference between having the data and being able to work with it.

---

The pipeline is built. Upload a document — any of these eleven types — and it returns immediately with `status: pending`. Everything else runs after the response is sent. The OCR, the type detection, the schema lookup, the field extraction, the FTS index update. If a document type has no schema, the status becomes `no_schema` and an investigation lead appears in the workspace: this document needs a schema before fields can be extracted.

The 990 XML files bypass OCR entirely. The IRS's XML has known element paths. `ReturnHeader/TaxYr` is always the tax year. `IRS990/GrossReceiptsAmt` is always the gross receipts. The extraction confidence is 1.0 because there's no interpretation — just parsing. Claude doesn't touch it.

Twenty-nine tests. All green.

That's the session. NLP search is next — turning "find all properties where the nonprofit paid more than twice the appraised value" into a query that actually runs.

---

*From Case to Code is a build journal. I'm building Verity Prism from scratch and writing down what I'm doing and why. If you've ever been buried in documents knowing the answer was in there somewhere — you know why this exists.*

*Follow along: `-corvus` on Hashnode.*
