# The Map

*By Corvus | From Case to Code*

---

The platform has an observability layer. It logs every Claude call — model, latency, input tokens, output tokens, call type, whether it succeeded — and feeds a dashboard showing automation rate, confidence trends, latency by document type, and failure count by batch.

Nine job descriptions called this LangSmith.

---

I'd been building in isolation with my own vocabulary. The extraction pipeline with confidence scoring and automated retry — that's what evaluation frameworks do. The document search layer, full-text search plus structured field filters — that's what people mean by retrieval pipelines. The call log table is LangSmith. The vector column I was about to add alongside the FTS index is PGVector, and running both together is called hybrid search.

Everything I'd built has a name. I just hadn't learned the names before I built it.

That's not a problem and it's not neutral. Building something from scratch means you understand every decision in it — why the call log uses an isolated session so logging failures never affect extraction, why the evaluator is a pure function with no DB access so it can be tested without a database, why the FTS index sits on the documents table instead of the extractions table. Every one of those choices was made for a reason and the reasons are all still in the code.

The tradeoff is that nobody reading a resume can see any of that. "Observability layer" and "LangSmith" look different to a hiring manager even when they're solving the same problem. The person who built it from scratch understands it better. The person who used the standard tool is immediately legible to everyone already using it. That's a real difference, not a cosmetic one.

---

Reading nine job descriptions against what the platform does separated two kinds of gaps: vocabulary gaps, where I'd solved the problem but named it differently, and real gaps, where the tool I'd built was actually missing something the market-standard version provides.

LangSmith does things the custom call log doesn't — per-call traces readable by someone who didn't write the logging code, session replay, comparison across runs. Not just observability in the abstract, but a specific interface for a specific workflow that's become standard on AI engineering teams. Adding it doesn't replace the call log, which feeds the billing metering layer. It adds a surface the log doesn't have.

PGVector alongside full-text search isn't a vocabulary fix — it's a genuine addition. FTS with field-level filters is more accurate than vector search for structured queries. A fraud investigator asking for all deeds where the sale amount exceeds twice the appraised value is running a SQL filter, not a semantic similarity problem. Vector search finds documents vaguely related to that idea. The filter finds the exact documents. But "find me documents similar to this one" or "what's in this workspace about property transfers" — those are semantic questions, and FTS doesn't help with those. You need both.

---

The question when you find the map is whether to rebuild from it or add to what's already there.

Rebuilding would mean replacing what works — swap the call log for LangSmith, replace full-text search with pure vector search, speak the vocabulary exactly. The story becomes cleaner. The tradeoff is real: pure vector search loses the structured query capability signal detection depends on, and ripping out the call log means ripping out the metering layer with it. You'd be starting clean in exactly the places where the existing foundation was strongest.

Adding means LangSmith wraps the existing Anthropic client — one line, transparent to every caller, the log stays. PGVector goes in alongside the FTS index, not instead of it. The platform gets both capabilities without breaking what was already working.

And here's the thing: hybrid search turns out to be the right architecture anyway, not a compromise between two options. Elasticsearch runs both indexes and routes based on query type. Pinecone added keyword search alongside vector search because customers kept needing it. The decision to build FTS first was correct for the queries the investigation use case actually runs. Adding semantic search makes the platform complete, not different. The "from scratch" build accidentally landed on the pattern the industry arrived at by iteration.

---

218 tests passing, PGVector column live with an ivfflat cosine distance index, LangSmith wired into the singleton, the call log still feeding metering. The hybrid search routes to FTS for structured questions and vector for semantic ones.

There's something useful about having built the thing from scratch first and then finding the map. The decisions that went into the custom implementation — isolated logging session, pure-function evaluator, FTS on the documents table — are still in the code, still right, and now legible to anyone who knows the vocabulary. The map didn't replace the terrain. It just made it possible to show someone where you are.

The platform was built for an investigation. The additions are built for both the investigation and everyone who needs to understand what was built from the outside. Those aren't different goals — they're the same platform doing two jobs at once.

---

*From Case to Code is a build journal. I'm building Verity Prism from scratch and writing down what I'm doing and why. If you've ever been buried in documents knowing the answer was in there somewhere — you know why this exists.*

*Posts 1 through 12 cover the origin, the data model, the extraction pipeline, the agentic chat engine, the expansion architecture, the UI layer, the audit, the review pane, and the first real case run.*

*Follow along: `-corvus` on Hashnode.*
