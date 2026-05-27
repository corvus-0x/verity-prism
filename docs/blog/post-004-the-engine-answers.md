# The Engine Answers

*By Corvus | From Case to Code*

---

The database throws an error when you try to change history.

Not a validation failure. Not a soft warning. A hard stop with a message I wrote myself: *audit_log rows are immutable — they cannot be modified or deleted.* I triggered it intentionally this session to confirm it holds. It holds.

That's the design working. Everything else this session was making sure the rest of the engine deserved that standard.

---

Before finishing the last two features, I stopped.

The pipeline had three problems I hadn't written tests for. None of them were visible yet — the code ran, the tests passed. But running the system against a real document instead of a mocked response revealed all three inside an hour.

The first: Claude wraps JSON in markdown code fences when you ask it not to. The response comes back as `` ```json\n{"document_type": "DEED"}\n``` `` instead of `{"document_type": "DEED"}`. The JSON parser chokes on the backticks. The document gets classified as OTHER and nothing gets extracted. The fix is a helper function that strips the fences before parsing — one function, imported wherever Claude's JSON gets parsed, so the versions can't drift.

The second: Claude uses `field` and `value` as key names when the prompt says to use `field_name` and `field_value`. The extraction runs, Claude does the work, but the save function looks for `field_name` and finds nothing. Zero fields stored. The fix is three layers: the prompt now says the key names explicitly, normalisation converts the variants immediately after parsing, and the save function still accepts both as a final catch. If Claude ignores the instruction, normalisation catches it. If normalisation misses something, the save function catches it. The same data makes it through regardless of what Claude decides to call the keys.

The third: the token limit was fixed at 2000. A deed has 64 fields. At roughly 100 tokens per field in the JSON output, that's 6,400 tokens needed. Claude wrote 2,000 tokens and stopped mid-string. The extraction failed silently. Raising the number to 4,096 fixes the deed but breaks the parcel record schema with 370 fields. The right fix is batching — 40 fields per Claude call, each call sized to its batch. A deed runs in two calls. A 370-field parcel record runs in ten. More API calls, but every call completes. Incomplete extraction that silently loses 300 of 370 fields is worse than nine extra calls.

None of these failures showed up in the test suite because the tests mock Claude. Mocked tests verify the pipeline logic — that the right functions get called in the right order with the right arguments. They don't verify that Claude behaves the way you expect. Live tests against the actual API do. The gap between "tests pass" and "works correctly with real data" is exactly that distance.

---

After the fixes, two features.

Search: a plain-English query goes to Claude with the list of field names extracted in the workspace. Claude translates it into structured filters. The backend runs those filters against the extracted field data — full-text search for the document text, direct field comparisons for things like "amount greater than X." One guard worth noting: when you filter by "greater than 100000," the system casts the extracted field value to a number. That crashes if the value is "unknown" or blank, which happens because documents are imperfect. A regex check before the cast skips anything that doesn't look like a number. The query still runs; it just doesn't crash on the noise.

Chat: Claude gets a text block containing every entity, every transaction, every finding, every open lead, every document name in the workspace. That block becomes the system prompt. The instruction says: answer from the data only, be precise with numbers and dates, when you see something uninvestigated flag it as a next lead.

The quality of the answers is proportional to the quality of the workspace data. An empty workspace gets generic answers. A workspace with uploaded documents, created entities, recorded transactions, and confirmed findings gets specific answers that trace back to exact fields. That's the design. The chat exists because the extraction had to be right first.

---

There was a larger decision this session about what this platform is.

It's an IDP platform. The fraud investigation tools — signal definitions, network graph, referral formats — are a cap that installs on top. An insurance customer installs the same engine with a different cap. They never see fraud signal logic. The engine doesn't know what fraud is. It processes documents.

The practical consequence: all eleven document schemas are now tagged "general." A schema describes how to extract fields from a parcel record or a deed — that extraction is the same operation regardless of domain. What a fraud investigation does with a lender ID that appears identically across fifteen connected properties is cap logic. The schema just gets the data right.

---

Thirty-five tests passing. Phase 1 backend complete.

The way I know it's complete: I uploaded a real deed, waited thirty seconds for the pipeline, and asked the system who transferred the property. It named the grantor, the grantee, the address, the attorney who prepared the instrument, and the date. From a scanned image. Without any of that data being typed in manually.

The audit log records that upload as a permanent event. You can't change it. That's the bar the trigger set. The rest of the session was earning it.

---

*From Case to Code is a build journal. I'm building Verity Prism from scratch and writing down what I'm doing and why. If you've ever been buried in documents knowing the answer was in there somewhere — you know why this exists.*

*Follow along: `-corvus` on Hashnode.*
