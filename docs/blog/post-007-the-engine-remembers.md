# The Engine Remembers

*By Corvus | From Case to Code*

---

The sidebar showed Transactions, Findings, Leads. Not for fraud workspaces. For all workspaces. The workspace creation function hardcoded `vertical: 'fraud'` on every new workspace, regardless of what you asked it to create. The visual layer had an opinion about what the platform was, and that opinion was wrong.

That part was easy to see. A WorkspaceContext to pass vertical down the component tree. A map of vertical-specific nav items keyed by vertical string. A creation modal that actually asks which vertical you want. The sidebar now shows engine-only items for a general workspace and adds fraud nav only when the workspace is fraud. More to set up than it sounds. Worth it.

But there was another kind of contamination that wasn't visible from the outside.

---

The extraction prompts are instructions the engine carries into every document it reads. They tell Claude what to look for, how to handle ambiguous values, what format to extract fields in. The DEED schema prompt explains how to compute an implied sale price from the conveyance fee. The PARCEL-RECORD prompt explains what to do with a date value that means "not recorded." The 990 prompt walks through the XML structure, element by element.

Embedded in those prompts, across several schemas, were specific names from the case the engine was built on. A county auditor deputy — named, in the description for that field, as an example of what to look for. A county name in multiple field descriptions as the example geographic value. A nonprofit's own subdivision name in the subdivision field description, as the example of what a subdivision looks like.

A county auditor deputy named by name. A county name across multiple fields. A nonprofit's own subdivision as the example value. Anyone reading the schema could trace back what investigation this engine was built on.

That came out the same session I found it.

The engine wasn't wrong to include them when it was built. They were accurate. Drawn directly from real documents. But an extraction prompt isn't documentation — it's instructions Claude reads before touching every document the engine processes. Across every future workspace. Every customer. Every vertical. The engine was carrying the specifics of one investigation into everything it would touch next.

---

The way to find them was to build the Schema Library.

Before it existed, the prompts and field descriptions lived in a seed file — 1,700 lines, one function per schema, shaped for a developer reading it, not a reviewer. The specific names were invisible by volume. You'd have to know what you were looking for. Build a page that renders every schema on a screen — display name, document type, field count, full field list with each description — and the case-specific content surfaces immediately. A person's name in a field description reads wrong in that context. A specific organization's own subdivision name as the example value reads wrong. You can see it when it's laid out. You can't see it in a file you're not looking at the right way.

Stripped them all out. Generic examples replaced specific ones. The seed functions were converted from skip-if-exists to upsert — re-running the script now updates existing records in the database rather than ignoring them. The Schema Library shows descriptions that could describe any document of that type, from any county, from any case.

---

The platform was built on one investigation. That's not a flaw — it's how you build something real rather than something hypothetical. A real case with real documents forces decisions you can't anticipate on paper. The schemas are as deep as they are because real documents were run through them.

But before the engine handles the next investigation, or the insurance vertical, or anything that isn't that case, the instructions it carries can't remember where it started.

The sidebar was the obvious version. The prompts were the version you had to build something to see.

Both are gone.

---

*From Case to Code is a build journal. I'm building Verity Prism from scratch and writing down what I'm doing and why. If you've ever been buried in documents knowing the answer was in there somewhere — you know why this exists.*

*The origin story, the data model, the extraction pipeline, the agentic chat engine, and the expansion architecture are in posts 1 through 6.*

*Follow along: `-corvus` on Hashnode.*
