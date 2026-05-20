# The Engine Answers

*By Corvus | From Case to Code*

---

Phase 1 is done. The backend is complete. And the way I know it's done is that I can type a question and get an answer.

Not a demo. Not a mocked response. A question about documents that were uploaded, extracted, and indexed — answered by Claude with the extracted field values from every document in the workspace as context. The answer is only as good as the data. The data is only as good as the pipeline. The pipeline has been running for three sessions now. This session I made it harder to break.

---

Before finishing, I stopped.

The pipeline had three problems I hadn't written tests for. None of them were visible yet — the system worked. But I'd been doing this long enough to know that "works now" and "holds under pressure" are different things. The schema lookup was vertical-blind. Both extraction paths returned different types that downstream code handled with an isinstance check. A database change from Task 8 lived only in the live database, not in any migration file.

The schema lookup problem was the one that mattered most. Every document that gets uploaded, the pipeline looks up a schema for its type. Right now all schemas are tagged "general" — they work for any workspace. But the architecture I'd settled on this session meant that eventually fraud workspaces would have fraud-specific schemas, and insurance workspaces would have insurance-specific schemas. Without the vertical-aware lookup, a fraud workspace could accidentally get an insurance schema. Silently. With the wrong field definitions. Producing extraction data that looks right but isn't.

Fixed it before it could happen. The lookup now takes the workspace's vertical, prefers a matching schema, falls back to general. Three lines of code that prevent a class of silent corruption that would have been very hard to trace later.

The isinstance check was a design smell. The XML parse path returned SQLAlchemy objects. The Claude extraction path returned dictionaries. The FTS indexing step had branching logic to handle both. Normalized it — both paths return the same format, same step saves both, no branching. Not because it was broken, but because two paths with different output types is a liability that grows over time.

The migration gap was administrative but real. A clean install would have been missing two database changes. Written the migration, made it idempotent, confirmed it applies correctly on a database where the changes already exist.

---

Then the last two features.

Search: a plain-English query goes to Claude with the list of every field name extracted in the workspace. Claude translates it into structured filters. The backend runs those filters against the extracted field data — FTS for the document text, direct field comparisons for things like "amount greater than X." The results come back with every extracted field value attached. The query "find all properties where the paid amount was more than twice the appraised value" becomes a filter: implied_sale_price > (appraised_value_current * 2). That filter runs against the rows in document_extractions, which are the output of every deed and parcel record that was uploaded and extracted.

One thing the plan didn't account for: the CAST to numeric. When you filter by "greater than 100000", PostgreSQL casts the extracted field value to a number. That crashes if the field value is "unknown" or "N/A" or blank — which happens, because documents are imperfect. Added a regex guard before the cast. Only values that look like numbers get cast. Everything else is skipped. The query still runs; it just doesn't crash on the imperfect data.

Chat: Claude gets a text block containing every entity, every transaction, every finding, every open lead, every document name in the workspace. That block becomes the system prompt. The history of the conversation is passed along with each message. Claude answers from the data. The system prompt says: be precise with numbers and dates, don't speculate beyond what the data shows, when you see something uninvestigated, flag it as a next lead.

The quality of the answers is proportional to the quality of the workspace data. An empty workspace gets generic answers. A workspace with uploaded deeds, 990s, parcel records, and UCC filings — with entities created, transactions recorded, findings confirmed — gets specific answers that trace back to exact documents and exact fields. That's the design. The chat isn't decorative. It's the reason the extraction had to be right.

---

There was a larger decision this session about what this platform is.

It's an IDP platform first. The fraud investigation tools are a cap that installs on top — signal definitions, network graph, referral export formats, investigation workflow. An insurance customer installs the same engine with a different cap. They never see fraud signal logic. The engine doesn't know what fraud is. It processes documents.

I'd described it the wrong way in the roadmap — some fraud features were listed as platform capabilities. Network graph. Investigation timeline. Those are fraud cap features. The engine provides entity and relationship storage. The fraud cap decides what a meaningful connection looks like in an investigation context and how to render it.

The practical consequence: all eleven document schemas are now tagged "general." They describe how to extract fields from a parcel record or a deed — that's the same operation regardless of domain. What a fraud investigation does with a lender ID that appears identically on fifteen connected properties — that's cap logic. The schema doesn't know about that. The extraction just gets the data right.

---

Thirty-five tests. All passing.

Audit log immutability confirmed: attempting to update an audit log row returns `ERROR: audit_log rows are immutable — they cannot be modified or deleted`. The database trigger holds. That error message is permanent record of the design working.

Phase 1 backend is done. The engine answers. Phase 2 is about connecting it to the world — public data sources, automated signal detection, the first vertical cap fully packaged. That's where the patterns start surfacing automatically instead of waiting to be found.

---

*From Case to Code is a build journal. I'm building Verity Prism from scratch and writing down what I'm doing and why. If you've ever been buried in documents knowing the answer was in there somewhere — you know why this exists.*

*Follow along: `-corvus` on Hashnode.*
