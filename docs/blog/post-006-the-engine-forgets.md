# The Engine Forgets

*By Corvus | From Case to Code*

---

The expansion plan started with a question: what breaks if a new vertical ships?

Not a customer. Not a deadline. Just the question, worked through on paper. The answer came back in three places. `KNOWN_DOCUMENT_TYPES` in `extraction_engine.py`. `DOC_TYPE_CODES` in `naming.py`. A function called `is_parseable_xml` that decided, from a hardcoded list, whether a document should bypass Claude and go straight to the XML parser. Three lists. Three places in code that knew what documents existed. None of them talked to the database.

That's not a platform. That's a fraud investigation tool wearing a platform's shape.

---

The database had the answer. `document_schemas` — one row per document type, with field definitions, parse strategy, confidence threshold. Every new type that gets added goes in there. The engine has been routing to that table since the first document went through. But the engine also had its own opinions, separate from the table, about what types were legal.

When you add an insurance form schema to the database, nothing changes in the engine. Detection still uses the old list. Naming still uses the old list. Routing still uses the hardcoded function. The schema row exists. The engine can't see it.

---

The fix is a function: `_load_known_types(db)`.

```python
rows = (
    db.query(DocumentSchema.document_type)
    .filter(DocumentSchema.is_active == True)
    .distinct()
    .all()
)
return [r[0] for r in rows] + ["OTHER"]
```

Called on every invocation of `detect_document_type`. The database answers; the engine passes that answer to Claude. Add a row, and at the next upload, Claude knows what the row is. No deploy. No list to update. No code to touch.

The same query went into `generate_standardized_name`. Same fix, same structure. Now there were no more hardcoded lists.

`is_parseable_xml` was different. It didn't just hold a list — it decided routing. A document is XML and its type is on the approved list, so skip Claude and parse it directly. The logic was right but the knowledge was wrong. Routing belongs to the schema. The `document_schemas` table already has a `parse_strategy` column for exactly this: `xml_direct` or `claude`. The pipeline reads it now. `is_parseable_xml` had nothing left to do.

Deleted.

---

Dead code is easy to miss when it works. `is_parseable_xml` was tested. The tests passed. It was deciding, correctly, which documents to route where. But it was maintaining its own list of XML-capable types, separate from the schema that already held that information, and those two lists could drift. The function contradicted the architecture it was sitting next to.

The schema is authoritative, or it isn't. Partial authority is a slow leak.

---

Adding a new document type to Verity Prism is now one operation: insert a row into `document_schemas`. The engine detects it. The engine names it correctly. The engine routes it to the right parser. The engine extracts against the field definitions in that row. The whole pipeline follows from one database row.

That's what the expansion plan was checking for. It found three places that said no. They're gone.

The next vertical has somewhere to land.

---

*From Case to Code is a build journal. I'm building Verity Prism from scratch and writing down what I'm doing and why. If you've ever been buried in documents knowing the answer was in there somewhere — you know why this exists.*

*The origin story, the data model, the extraction pipeline, and the agentic chat engine are in posts 1 through 5.*

*Follow along: `-corvus` on Hashnode.*
