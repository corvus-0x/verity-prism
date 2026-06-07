# The Engine Asks

*By Corvus | From Case to Code*

---

The chat function had one job: take a question, load everything, ask Claude.

"Everything" meant building a text block — entities, transactions, findings, open leads, documents — and handing it to Claude as context before each response. Claude read the whole workspace before answering any question. An investigator asks who signed the deed. Claude reads the financial transactions first. Then the entity list. Then the findings. Then the leads. Then the documents. Then it answers about the deed.

It worked. Thirty-five passing tests said so.

---

The problem with reading everything is that it costs whether or not it's needed. And more than that: it assumed the workspace data was current enough and complete enough to answer anything. If the extraction pipeline missed a field, the chat didn't know what it was missing. It answered from what the context block contained, which was whatever the context builder grabbed.

The right model is tools. Claude knows what tools it has. When it needs data, it calls a tool. When the tool returns empty, Claude knows the data isn't there — that's different from the data not being in the context block, which looks the same as the data not existing at all.

Six tools: `search_documents`, `get_entity`, `query_extractions`, `get_transactions`, `get_findings`, `get_leads`. Ten rounds before a synthesis pass forces an answer. The system prompt stayed short — workspace name, vertical, a few behavioral instructions. One of them: reference documents by filename, not by ID.

---

The tools went in. Tests passed — three integration tests covering the full round trip through the router, plus twenty-seven unit tests for each tool individually. Everything green.

Then a second review pass ran against the spec. `query_extractions` was returning `document_id`, `field_name`, `field_value`. The system prompt said: reference by filename. The tool wasn't returning one.

Claude would have complied with the instruction as best it could. "Based on document 3a8f2c..." Not wrong. Not what the system said it would do. The system prompt shifted what Claude was trying to produce. It didn't change what the tool returned.

That one needed a join.

---

There were four others.

The `get_leads` tool was returning `lead.originated_by` mapped to a key called `source`. The model has both — `source` is a free-text field, `originated_by` is an enum. They mean different things. The implementation had read the enum. The tests confirmed the count was correct and the status was right. Nobody had asserted on the value of `source`. The bug survived all twenty-seven tests.

A financial tool was serializing `amount_paid` with a falsy check: `str(t.amount_paid) if t.amount_paid else None`. In Python, `bool(Decimal("0"))` is `False`. A zero-consideration deed — real and common, appears in every property-to-family transfer in the investigation — would have come back with `amount_paid: null`. Correct column. Wrong value.

The router was saving the user message to the database before calling `chat()`. Inside `chat()`, conversation history loads from the database. The newly committed message was already in history before being appended again. First message in a conversation: fine. Second message: Claude receives the same user turn twice in sequence. The test covered a fresh conversation. The bug only appeared on the second turn.

When a tool fails, the Anthropic API has a specific signal: `is_error: true` on the `tool_result` block. Without it, an error message embedded in a tool result looks like a valid response. Claude may continue reasoning from it instead of trying something else. The flag was missing from every failed tool call.

---

Five bugs. All caught before the code ran against a real question.

The tests weren't wrong. They tested what they were written to test. The implementation was correct by the spec that was written. The spec had gaps that nobody noticed until something read it line by line against the code.

The filename one is the one that stays with me. Not mechanical, like a missing flag or a wrong column — structural. The system prompt said one thing. The tool implementation made it impossible. Both committed. Both tested. Both green.

Prompts describe what you want the system to do. They don't make the system capable of it.

---

Sixty-seven tests. The loop runs. An investigator asks "who are the grantors on every deed in this workspace" and Claude calls `query_extractions` with `field_name: "grantor"`, pulls back the rows with filenames attached, and answers from the data. One round. A harder question might take three.

What it can't do yet: write anything back. No new findings. No new leads. The tools are read-only.

That's next.

---

*From Case to Code is a build journal. I'm building Verity Prism from scratch and writing down what I'm doing and why. If you've ever been buried in documents knowing the answer was in there somewhere — you know why this exists.*

*The extraction pipeline and the first version of chat are in posts 3 and 4. The origin story is in post 1.*

*Follow along: `-corvus` on Hashnode.*
