# Phase 1 — Core Foundation Design Spec
**Project:** Intelligent Document Processing Platform (working title: Verity Prism)
**Date:** 2026-05-17
**Author:** Tyler Collins
**Status:** Approved

---

## How to Read This Spec

This document is written for a junior developer — you — who will be building every line of this platform and needs to understand not just what to build, but why every decision was made.

Each section follows this pattern:
- **What it is** — the plain-English description
- **Why we built it this way** — the reasoning behind the choice
- **What it does in practice** — a concrete example from the real investigation

If a technical term appears for the first time, it's explained inline. There is no assumed knowledge beyond what you learned in your IBM full stack certificate.

---

## 1. What This Platform Does

This is an **Intelligent Document Processing (IDP) platform**. That means it takes documents — PDFs, images, forms, spreadsheets — and automatically pulls out every piece of useful information inside them, organizes that information in a database, and lets you search and ask questions about it in plain English.

Think about what you did manually during your investigation: you downloaded a PDF from the county auditor, read through it, and noted that Karen Homan paid $300,000 for a property worth $37,490. This platform does that reading and noting automatically, for every document, every time.

**The three things it does above all else:**
1. **Extracts everything** — reads every document and pulls out every name, date, dollar amount, address, and ID number into structured database fields you can search
2. **Makes it findable** — lets anyone search all that information using plain English, not technical queries
3. **Enables vertical logic** — the fraud investigation tools (signals, findings, leads) are built on top of this foundation. So is the future insurance vertical.

This platform was built from a real fraud investigation (Do Good In His Name Inc, EIN 82-4458479, Darke County OH). That investigation is **Vertical 1** — the first specific use case. Insurance form automation is **Vertical 2**. Other industries follow the same pattern.

**Evidence integrity is non-negotiable.** Every document, every change, every search is permanently recorded. The data must be able to stand up in court.

---

## 2. Platform Phases

This platform is too large to build all at once. We break it into four phases. Each phase produces working software before the next one starts. This is how professional software teams work — ship something real, then build on it.

| Phase | Name | What it covers |
|-------|------|---------------|
| **1** | Core Foundation | The IDP engine: ingest documents, extract every data point, search in plain English, manage workspaces, AI chat, evidence integrity — plus Vertical 1 (fraud investigation) |
| **2** | Investigation Intelligence | Pull data automatically from public sources (IRS, state records, county), guided AI investigation workflow, visual network map of connections, timeline view |
| **3** | Collaboration & Output | Team logins, generate referral packages for AG/IRS/FBI/FCA, Vertical 2 (insurance automation), share cases with lawyers and journalists |
| **4** | Scale & Deployment | Move to AWS, handle more users, add more verticals and integrations |

**This document covers Phase 1 only.** We do not design Phase 2 until Phase 1 is done and working.

---

## 3. Who Uses This

- **Right now:** You, working alone on one case at a time
- **Phase 1 goal:** You + 1–3 teammates (a lawyer, a journalist, a colleague) on the same workspace
- **Vertical 1 users:** Whistleblowers, investigators, journalists, lawyers
- **Vertical 2 users:** Insurance company staff — the ones currently entering form data by hand into multiple systems
- **Long-term path:** Any industry where people spend time manually reading documents and re-entering data

---

## 4. Tech Stack

Every technology choice here was made deliberately. Here is what we use and why.

| Layer | Technology | Why this choice |
|-------|-----------|-----------------|
| **Frontend** | React + Vite | You know React from your IBM cert. Vite is a faster modern build tool than Create React App. |
| **Backend** | Python + FastAPI | Python is the strongest language for AI and document processing. FastAPI is modern, fast, and has automatic API documentation built in — you'll see your API as a webpage while you build it. |
| **Database** | PostgreSQL | A relational database — data is stored in tables with defined relationships, like a very powerful spreadsheet. PostgreSQL also has built-in full-text search, so we don't need a separate search system in Phase 1. |
| **Full-text search** | PostgreSQL tsvector | Built into PostgreSQL. Lets you search the content of documents like Google searches the web — finds words and phrases across all your text. No extra software needed. |
| **File storage** | Local disk → AWS S3 | Files (PDFs, images) are stored on disk during development. When we deploy to AWS, they move to S3 (Amazon's file storage service). The code doesn't change — just a config setting. |
| **AI** | Claude API | Claude reads documents, extracts structured data, translates plain English into database queries, and powers the chat feature. |
| **OCR** | PyMuPDF + Tesseract | OCR stands for Optical Character Recognition — it reads text from PDFs and images. PyMuPDF handles PDFs that have embedded text. Tesseract handles scanned documents (images of pages). |
| **Auth** | JWT tokens | JWT (JSON Web Token) is the industry standard for "prove who you are" without sending your password on every request. You log in once, get a token, and send the token with every API call. |
| **Containers** | Docker + docker-compose | Docker packages your app and all its dependencies into a container — a self-contained environment that runs the same on your laptop and on AWS. `docker-compose up` starts everything with one command. |
| **Deployment** | AWS (Phase 4) | Amazon Web Services hosts the production version. We design for it from day one so moving from local to AWS requires minimal changes. |

---

## 5. Architecture — Five Layers

**What is architecture?** Architecture is the blueprint for how the parts of your system connect. Think of it like the floorplan of a building — it shows what rooms exist, how they connect, and what happens in each one.

This platform has five layers. Each layer has a single clear job and talks to the layers next to it through well-defined interfaces.

```
┌─────────────────────────────────────────────────┐
│              DOCUMENT SOURCES                    │
│  File Upload | API Pull | Email | Form | XML     │
└─────────────────────┬───────────────────────────┘
                      │ documents come in here
                      ▼
┌─────────────────────────────────────────────────┐
│         LAYER 1 — INGESTION                     │
│                                                  │
│  • Detect file type (PDF? image? XML?)           │
│  • Generate SHA-256 hash FIRST (evidence lock)   │
│  • Store file to disk or S3                      │
│  • Write first audit log entry                   │
└─────────────────────┬───────────────────────────┘
                      │ raw file + hash
                      ▼
┌─────────────────────────────────────────────────┐
│   LAYER 2 — DEEP EXTRACTION PIPELINE            │
│                           ← THE IDP CORE        │
│  ① OCR: read every word on every page           │
│  ② Detect document type (deed? 990? UCC?)       │
│  ③ Extract every field using AI                 │
│     → grantor_name, amount_paid, parcel_number  │
│     → one database row per extracted field       │
│  ④ Update search index with all content         │
└─────────────────────┬───────────────────────────┘
                      │ structured data
                      ▼
┌─────────────────────────────────────────────────┐
│    LAYER 3 — KNOWLEDGE BASE + SEARCH            │
│                                                  │
│  PostgreSQL database:                            │
│  • All documents + their extracted fields        │
│  • Entities, relationships, transactions         │
│  • Findings, leads, conversations, audit log     │
│                                                  │
│  NLP Search:                                     │
│  • User types plain English                      │
│  • Claude translates to a database query         │
│  • Results come back instantly                   │
└─────────────────────┬───────────────────────────┘
                      │ organized, searchable data
                      ▼
┌─────────────────────────────────────────────────┐
│       LAYER 4 — VERTICAL MODULES                │
│                                                  │
│  Fraud Investigation (Vertical 1 — now)         │
│  • Signal types (SR-003, SR-025, etc.)           │
│  • Findings and evidence chains                  │
│  • Investigation leads and workflow              │
│                                                  │
│  Insurance Automation (Vertical 2 — Phase 3)    │
│  • Form data extraction and routing              │
│  • Error flagging, system integration            │
└─────────────────────┬───────────────────────────┘
                      │ processed, analyzed data
                      ▼
┌─────────────────────────────────────────────────┐
│         LAYER 5 — USER INTERFACE                │
│                                                  │
│  NLP Search Bar (on every screen)                │
│  Workspace Dashboard | Document Viewer           │
│  Entity Manager | Findings Board | AI Chat       │
└─────────────────────────────────────────────────┘
```

**Evidence integrity runs across all layers:** Every document is hashed the moment it arrives. Every action by every user is permanently recorded. No record is ever deleted — only marked as deleted while the original stays in the database.

---

## 6. Data Model

**What is a data model?** It's a description of every table in the database, what columns each table has, and how tables relate to each other. Think of each table as a spreadsheet tab. The relationships are like the links between those tabs.

**Why do we use PostgreSQL (relational) instead of something like MongoDB (document-based)?** Because our data is deeply interconnected. A document is linked to a workspace, which is linked to entities, which are linked to relationships and transactions, all of which link to a permanent audit log. A relational database enforces these connections — it won't let you create a finding that points to a document that doesn't exist. That integrity matters for court-admissible evidence.

---

### 6.1 users
Who can log in to the platform.

```
id              — unique identifier (UUID format: a3f2-... random, globally unique)
email           — login email, must be unique across all users
password_hash   — we NEVER store the actual password, only a one-way hash of it
full_name       — display name
role            — "owner" (can do everything) or "member" (limited permissions)
created_at      — when this account was created (server sets this, not the client)
```

**Why UUID for IDs?** UUIDs (like `a3f2b1c4-...`) are random and globally unique. Using sequential numbers (1, 2, 3...) would let someone guess other users' IDs. UUIDs prevent that.

**Why hash passwords?** If the database were ever compromised, hashed passwords are useless to an attacker. We use bcrypt, which is a slow hashing algorithm designed specifically for passwords — it's intentionally slow to make brute-force attacks impractical.

---

### 6.2 workspaces
A workspace is the container for an investigation or a project. In the fraud vertical, the UI calls this a "Case." In the insurance vertical, it would be called a "Project" or "Batch." The backend always calls it a workspace.

```
id              — unique identifier
name            — "Do Good In His Name Inc" or "March 2026 Auto Claims Batch"
description     — longer explanation of what this workspace is for
subject_name    — the main subject (fraud: the organization; insurance: policy holder)
jurisdiction    — where this applies (fraud: "Darke County, OH"; insurance: a region)
vertical        — "fraud", "insurance", or "general"
status          — "active", "closed", or "archived"
created_by      — which user created this workspace
created_at      — when it was created
updated_at      — when it was last changed
```

---

### 6.3 workspace_members
Controls who has access to which workspace. Without a row in this table, a user cannot see or access a workspace — even if they know its ID.

```
id              — unique identifier
workspace_id    — which workspace
user_id         — which user
role            — "owner" (full control), "analyst" (read/write), "viewer" (read only)
added_at        — when this person was added
```

**Why a separate members table?** This pattern is called a "join table" or "junction table." It lets one user belong to many workspaces, and one workspace have many users, without duplicating data. This is standard relational database design.

---

### 6.4 document_schemas ← NEW — IDP core
**This table is the instruction manual for the AI.** It tells Claude exactly what to look for when reading each type of document. Every document type (deed, 990, UCC filing, insurance form) has its own schema defining the fields to extract.

```
id                — unique identifier
document_type     — "DEED", "990", "UCC", "INSURANCE-FORM", etc.
vertical          — which vertical this schema belongs to ("fraud", "insurance", "general")
display_name      — human-readable label ("Warranty Deed", "IRS Form 990")
schema_fields     — JSON list of fields to extract (see example below)
extraction_prompt — the exact instructions sent to Claude when processing this doc type
version           — version number; increment this when you update a schema
is_active         — true/false; lets you disable a schema without deleting it
created_at        — when this schema was created
```

**Why store the extraction prompt in the database instead of hardcoding it?** Because prompts need to evolve. As you process more documents and find edge cases, you'll improve the prompt. Storing it in the database means you can update it without redeploying code.

**Example schema_fields for a Deed:**
```json
[
  {
    "name": "grantor_name",
    "type": "name",
    "description": "The person or entity giving up the property (the seller)",
    "required": true,
    "example": "Do Good Real Estate LLC"
  },
  {
    "name": "grantee_name",
    "type": "name",
    "description": "The person or entity receiving the property (the buyer)",
    "required": true,
    "example": "Karen Homan"
  },
  {
    "name": "consideration_amount",
    "type": "currency",
    "description": "The amount paid for the property",
    "required": true,
    "example": "300000.00"
  },
  {
    "name": "property_address",
    "type": "address",
    "description": "Street address of the property being transferred",
    "required": false,
    "example": "47 Patterson St, Osgood OH 45351"
  },
  {
    "name": "parcel_number",
    "type": "id",
    "description": "County assessor parcel ID number",
    "required": false,
    "example": "M51-2-312-12-01-01-12300"
  },
  {
    "name": "instrument_number",
    "type": "id",
    "description": "The recorder's instrument number — how this deed is filed at the courthouse",
    "required": false,
    "example": "202300004871"
  },
  {
    "name": "recording_date",
    "type": "date",
    "description": "The date this deed was officially recorded",
    "required": true,
    "example": "2022-09-15"
  },
  {
    "name": "deed_type",
    "type": "text",
    "description": "The type of deed: warranty, quitclaim, etc.",
    "required": false,
    "example": "General Warranty Deed"
  },
  {
    "name": "preparing_attorney",
    "type": "name",
    "description": "The attorney who prepared this deed",
    "required": false,
    "example": "Thomas L. Guillozet"
  },
  {
    "name": "notary_name",
    "type": "name",
    "description": "The notary public who witnessed the signing",
    "required": false,
    "example": "Randall Bruns"
  }
]
```

---

### 6.5 documents
Every file that enters the system — PDFs, images, spreadsheets. The raw document lives on disk; this table holds everything the system knows about it.

```
id                  — unique identifier
workspace_id        — which workspace this document belongs to
filename            — the standardized name Claude generated (see §7)
original_filename   — exactly what was uploaded — NEVER changes
file_path           — where the file is stored on disk or S3
file_type           — "pdf", "image", "csv", "text", "xml", or "other"
sha256_hash         — the document fingerprint, generated BEFORE anything else happens
source_url          — if pulled from an API (e.g. IRS TEOS), the URL it came from
source_type         — "upload" (you put it there), "api_pull" (system fetched it), "manual_entry"
detected_doc_type   — what Claude determined this document is ("DEED", "990", "UCC", etc.)
schema_id           — which extraction schema was used
ocr_text            — the complete text extracted from the document
search_vector       — a special PostgreSQL column for full-text search (auto-updated)
metadata_           — a flexible JSON field for anything that doesn't fit other columns
size_bytes          — file size in bytes
extraction_status   — "pending" (just uploaded), "complete" (extraction done), "failed"
uploaded_by         — which user uploaded this
uploaded_at         — when it was uploaded — NEVER changes
```

**What is SHA-256?** SHA-256 is a mathematical function that takes any file and produces a unique 64-character string (the hash). The same file always produces the same hash. A file that's been changed even by one character produces a completely different hash. This is how we prove in court that a document hasn't been tampered with after we collected it.

**What is tsvector?** It's PostgreSQL's internal format for full-text search. When you update `search_vector`, PostgreSQL breaks the text into searchable tokens and indexes them — similar to how Google indexes web pages. The `GIN` index on this column makes searches fast even with millions of words.

---

### 6.6 document_extractions ← NEW — ★ THE KEY IDP TABLE
**This is the most important table in the platform.** Every piece of structured information pulled from every document lives here — one row per field. This is what separates an IDP platform from a simple document storage system.

```
id              — unique identifier
document_id     — which document this came from
workspace_id    — which workspace (stored here too so searches are faster)
field_name      — the name of the field: "grantor_name", "consideration_amount", etc.
field_value     — the actual extracted value, always stored as text
field_type      — what kind of data this is: "name", "date", "currency", "address",
                  "id_number", "text", or "boolean"
confidence      — how confident Claude is in this extraction, from 0.0 to 1.0
                  (0.9 means very confident; 0.4 means uncertain — flag for review)
schema_id       — which schema defined this field
extracted_at    — when this extraction happened
```

**Why one row per field instead of one row per document?** Because you need to search fields individually. If you stored all extracted fields as one JSON blob per document, you couldn't ask "find all documents where consideration_amount > 200000" without reading every document. With one row per field, that query is a simple database filter.

**A deed with 11 fields = 11 rows in this table. A 990 with 60 fields = 60 rows. Every single one is searchable.**

**Index strategy** (indexes make searches fast — like a book's index vs. reading every page):
- Index on `(workspace_id, field_name)` — "find all grantor_names in this workspace"
- Index on `(document_id, field_name)` — "find all fields for this specific document"
- Full-text index on `field_value` — keyword search within field values

---

### 6.7 entities
The people, organizations, and properties that appear in a workspace. Often auto-populated from document extractions — if Claude extracts "Karen Homan" as a grantor on 5 deeds, the system can suggest creating a Person entity for her.

```
id           — unique identifier
workspace_id — which workspace
type         — "person", "organization", "property", or "financial_account"
name         — "Karen Homan", "Do Good In His Name Inc", "47 Patterson St"
status       — "active", "dissolved" (orgs), "deceased" (persons), "unknown"
data         — flexible JSON for type-specific details:
               person: {dob, address, ssn_last4}
               organization: {ein, sos_id, state_of_incorporation}
               property: {parcel_number, appraised_value, county}
is_deleted   — true if marked deleted (we never actually delete — see evidence integrity)
deleted_at   — when it was marked deleted
created_by   — who created this entity
created_at   — when it was created
```

**What is JSONB?** It's PostgreSQL's format for storing JSON data with indexing support. We use it for the `data` field because every entity type has different fields — a person has a date of birth, a property has a parcel number. JSONB lets us store any structure without needing a new database column for every possible field.

---

### 6.8 relationships
Connections between two entities. Every relationship is sourced to the document that proves it — you can always answer "how do you know this?"

```
id              — unique identifier
workspace_id    — which workspace
entity_a_id     — the first entity
entity_b_id     — the second entity
type            — how they're connected: "officer_of", "owns", "family_of",
                  "transacted_with", "employed_by", "lien_on", "legal_counsel_for"
                  (this list is extensible — add new types without changing the database)
description     — plain English explanation: "President/Treasurer, $0 salary"
start_date      — when this relationship began (nullable)
end_date        — when it ended — null means it's still active
source_doc_id   — the document that proves this relationship exists
created_by      — who added this
created_at      — when it was added
```

---

### 6.9 transactions
Financial flows between entities. Structured as their own table (not buried in JSONB) so you can sort, filter, and analyze them.

```
id                  — unique identifier
workspace_id        — which workspace
entity_from_id      — who paid or transferred (nullable)
entity_to_id        — who received (nullable)
transaction_type    — "purchase", "transfer", "lien", "loan", "donation",
                      "construction", or "compensation"
amount_paid         — what was actually paid (nullable)
appraised_value     — what the property was worth at the time (nullable)
consideration       — "zero", "below_market", "fair_market", or "above_market"
                      (auto-calculated from amount_paid vs appraised_value)
transaction_date    — when the transaction happened
recorded_date       — when it was officially recorded (deeds, liens)
instrument_number   — the official document number (e.g. Inst. 202300004871)
source_doc_id       — the document that proves this transaction
notes               — anything that doesn't fit the other fields
created_by          — who entered this
created_at          — when it was entered
```

**Why separate `amount_paid` from `appraised_value`?** This is how you catch overpayments and underpayments automatically. When Karen Homan paid $300,000 for a property appraised at $37,490, that's `amount_paid = 300000` and `appraised_value = 37490` — an 800% overpayment. With structured fields, the system can flag this automatically.

---

### 6.10 signal_types (Vertical 1 — fraud only)
A lookup table defining the categories of suspicious patterns the fraud vertical watches for. These codes come from the real investigation.

```
id              — unique identifier
code            — "SR-003" — the shorthand reference code
name            — "VALUATION_ANOMALY" — the machine-readable name
description     — full explanation of what this pattern means
severity        — "critical", "high", "medium", or "low"
relevant_to     — which agencies care about this: ["IRS", "AG", "FBI", "FCA"]
```

**Pre-loaded signal types from the Do Good investigation:**

| Code | Name | Severity | Relevant To |
|------|------|----------|-------------|
| SR-003 | VALUATION_ANOMALY | critical | AG, IRS |
| SR-004 | UCC_BURST | high | FCA, FBI |
| SR-005 | ZERO_CONSIDERATION | critical | AG, IRS |
| SR-015 | DEED_TITLE_DEFECT | high | AG |
| SR-021 | REVENUE_SPIKE | medium | IRS |
| SR-024 | CHARITY_CONDUIT | critical | IRS, AG, FBI |
| SR-025 | FALSE_DISCLOSURE | critical | IRS, AG |
| SR-026 | CONSTRUCTION_OVERAGE | high | IRS, AG |

---

### 6.11 findings (Vertical 1 — fraud only)
A confirmed investigative signal — something you've determined is worth reporting.

```
id              — unique identifier
workspace_id    — which workspace
signal_type_id  — which signal type this finding is (nullable — can be a custom finding)
title           — "47 Patterson St — 700% overpayment to Winner Kyle J"
description     — full explanation of what was found
severity        — "critical", "high", "medium", or "low"
status          — "open" (flagged), "confirmed" (verified), "dismissed" (not a problem)
created_by      — who created this finding
created_at      — when it was created
```

---

### 6.12 finding_evidence (Vertical 1 — fraud only)
Links a finding to the exact documents and entities that prove it. This is the evidentiary chain — the answer to "how do you know?"

```
id              — unique identifier
finding_id      — which finding this evidence supports
document_id     — the document that proves it (nullable)
entity_id       — the entity involved (nullable)
note            — what specifically in this document supports the finding
added_by        — who attached this evidence
added_at        — when it was attached
```

---

### 6.13 investigation_leads (Vertical 1 — fraud only)
Every investigative step — the question asked, the source checked, what was found, what it opened. This is the investigation workflow tracker.

```
id                  — unique identifier
workspace_id        — which workspace
question            — "Does Karen Homan have related businesses in Ohio?"
source              — "Ohio SOS" — where you looked for the answer
status              — "pending", "in_progress", "complete", or "dead_end"
originated_by       — "user" (you thought of it), "ai" (Claude suggested it), "external_tip"
triggered_by_id     — which other lead opened this one (self-referencing)
assigned_to         — which user is working this lead (nullable)
result_summary      — "Found Do Good Real Estate LLC (SOS #4371988)"
created_at          — when this lead was created
completed_at        — when it was resolved (nullable)
```

---

### 6.14 notes
Free-form text annotations attached to anything in the workspace. For the observations that don't fit a structured field.

```
id              — unique identifier
workspace_id    — which workspace
author_id       — who wrote this note
entity_type     — what kind of thing this note is about:
                  "workspace", "entity", "document", "finding", "transaction", "lead"
entity_id       — the specific ID of that thing
content         — the actual note text
created_at      — when it was written
```

**Example:** "Address digit sequence reversed — 6172 vs 6712 Olding Rd — likely same property or adjacent. Investigate."

---

### 6.15 ai_conversations + ai_messages
Chat history with the AI assistant, scoped to a workspace. Stored so you can come back to a conversation days later and continue where you left off.

```
-- ai_conversations (one thread of conversation)
id              — unique identifier
workspace_id    — which workspace this conversation is about
user_id         — who started this conversation
title           — auto-generated from the first message you send
created_at      — when the conversation started

-- ai_messages (individual turns within a conversation)
id                  — unique identifier
conversation_id     — which conversation this belongs to
role                — "user" (your message) or "assistant" (Claude's response)
content             — the actual message text
created_at          — when this message was sent
```

---

### 6.16 audit_log
**The most important table for legal integrity.** Every action taken in the platform — upload a document, change an entity, run a search, log in, log out — writes a permanent row here. Rows in this table can never be changed or deleted. This is enforced at the database level, not just in code.

```
id              — unique identifier
workspace_id    — which workspace this action relates to (nullable — some actions are platform-wide)
user_id         — who did it
action          — what happened: "created", "updated", "deleted", "uploaded",
                  "extracted", "searched", "queried", "login", "logout"
entity_type     — what kind of thing was affected: "document", "entity", "finding", etc.
entity_id       — the specific ID of the thing that was affected
before_state    — a JSON snapshot of what the data looked like BEFORE the change
after_state     — a JSON snapshot of what the data looks like AFTER the change
ip_address      — the IP address of the user who took this action
timestamp       — when it happened — set by the server, never by the client
```

**Why is this append-only?** In a legal proceeding, the opposing party will ask: "How do you know this document wasn't altered after you collected it?" The audit log is your answer. It shows exactly when the document arrived, who uploaded it, and that nothing has changed since. A database trigger (a piece of code that runs inside PostgreSQL itself) makes it physically impossible to update or delete any row in this table — even if someone compromises the application code.

---

## 7. Document Naming Scheme

When you upload a document, Claude reads its content and renames it to a standardized format. The original filename is always preserved and never changes.

**Format:**
```
[DATE]_[DOC-TYPE]_[PRIMARY-ENTITY]_[BRIEF-DESCRIPTION].[ext]
```

**Real examples from the Do Good investigation:**
```
2024-01-03_DEED_DoGoodRealEstate_25-W-Main-St.pdf
2022-09-15_990_DoGoodInHisName_TaxYear2021.pdf
2019-08-22_SOS-FILING_DoGoodRealEstateLLC_Formation.pdf
2020-07-17_UCC_HomanJay_SBA-EIDL-Lien.pdf
2023-03-28_DEED_DoGoodInHisName_135-Elm-St-Overpayment.pdf
```

**Why standardize names?** When you have 47 documents in a case, names like "scan0047.pdf" and "document(3).pdf" become useless. A standardized name tells you what the document is without opening it.

**Document type codes:**
`DEED` `990` `990-T` `UCC` `SOS-FILING` `BUILDING-PERMIT` `INSURANCE-FORM` `COURT-FILING` `AUDIT-REPORT` `CORRESPONDENCE` `OBITUARY` `NEWS-ARTICLE` `SCREENSHOT` `SPREADSHEET` `OTHER`

You can always override the AI-generated name. The original filename never changes regardless.

---

## 8. UI Structure

### 8.1 The NLP Search Bar — Most Important Feature
A search bar appears prominently on every screen. You type plain English. The results come back instantly.

**Example queries anyone can type:**
- *"find all property transfers for zero dollars"*
- *"show me documents mentioning Karen Homan"*
- *"list all deeds where the paid amount was more than double the appraised value"*
- *"what documents were filed between 2019 and 2022 in Darke County"*
- *"find insurance forms missing a policy number"*

Claude reads the query, figures out what you mean, translates it to a database query, and returns matching documents with the relevant fields highlighted. No SQL required. No training required.

### 8.2 Workspaces Home
The first screen after login. All your workspaces displayed as cards. Each card shows:
- Workspace name and subject
- Document count (and how many are fully extracted)
- Entity count
- Finding count (fraud vertical)
- Status badge (Active / Closed / Archived)
- A "+ New Workspace" button

### 8.3 Inside a Workspace — 8 Sections
Every workspace has a left sidebar with 8 sections. The main content area changes depending on which section you're in.

| Section | What it shows | Who uses it |
|---------|--------------|-------------|
| **Overview** | Summary stats, AI suggestions, recent activity | Everyone |
| **Documents** | Every document — upload new ones, browse existing, click to view full text and all extracted fields | Everyone |
| **Search** | The full NLP search experience — query box, filters, results with highlighted matches | Everyone |
| **Entities** | All persons, organizations, and properties — tabbed by type, each links to related documents | Everyone |
| **Transactions** | Financial flows between entities — sortable table, flagged anomalies highlighted in red | Everyone |
| **Findings** | The signal board — SR-XXX codes, severity badges, evidence chains (fraud vertical) | Fraud investigators |
| **Leads** | Investigation workflow — what's been checked, what's pending, what each step opened | Fraud investigators |
| **AI Chat** | Conversation threads with Claude — Claude knows everything in this workspace | Everyone |

---

## 9. Key Workflows

A workflow is the sequence of steps the system takes to accomplish a task. Understanding these will help you understand why the code is structured the way it is.

### 9.1 Document Ingestion + Deep Extraction

This is the most important workflow in the platform. It runs every time a document is uploaded.

```
Step 1:  User uploads a file (PDF, image, spreadsheet)

Step 2:  SHA-256 hash generated IMMEDIATELY
         → This is the evidence lock. The hash proves the file hasn't changed.
         → Nothing else happens until the hash is saved.

Step 3:  File written to disk (dev) or S3 (production)
         → The original file is preserved exactly as uploaded.

Step 4:  OCR runs
         → PyMuPDF extracts text from PDFs that have embedded text
         → Tesseract reads scanned images (photos of pages)
         → Result: the full text of the document as a string

Step 5:  Claude detects the document type
         → Reads the OCR text
         → Determines: is this a deed? A 990? A UCC filing?
         → Selects the matching extraction schema from document_schemas

Step 6:  Claude extracts every field from the schema
         → Reads the document text against the schema
         → Fills in every field: grantor_name, consideration_amount, recording_date...
         → Returns a confidence score for each field
         → Each field is written as one row in document_extractions

Step 7:  Claude generates the standardized filename
         → Uses the extracted data to produce: 2024-01-03_DEED_DoGoodRealEstate_...

Step 8:  Search index updated
         → documents.search_vector is updated with the full OCR text
           plus all extracted field values
         → This makes everything findable immediately

Step 9:  Document record saved
         → All metadata saved to the documents table
         → extraction_status set to "complete"

Step 10: Audit log entry written
         → Records: who uploaded it, when, what file, what hash

Step 11: Extracted fields shown to user for review
         → User can confirm, correct, or flag low-confidence extractions
         → Any correction is logged in the audit log
```

### 9.2 NLP Search

```
Step 1:  User types: "find all property transfers for zero dollars"

Step 2:  Backend sends this to Claude with context:
         "Translate this query for our database. The document_extractions table
          has columns: field_name (text), field_value (text).
          The documents table has a search_vector column for full-text search.
          Common field names include: consideration_amount, grantor_name,
          grantee_name, recording_date, parcel_number..."

Step 3:  Claude returns a structured query:
         {
           "extractions_filter": {"field_name": "consideration_amount", "field_value": "0"},
           "doc_type_filter": "DEED"
         }

Step 4:  Backend executes the query against the database
         → Combines the extraction filter with the full-text search
         → Returns matching document IDs

Step 5:  Results returned to UI
         → Document cards with the matched fields highlighted
         → Clicking a card opens the document viewer

Step 6:  Search logged in audit_log
         → Query text, result count, user, timestamp — all recorded
```

### 9.3 AI Chat

Every time you send a message to Claude in the chat, the system loads the entire workspace context first:

- Workspace name, subject, jurisdiction, status
- Every entity and its key data
- Every transaction with amounts and flags
- Every finding and open lead (fraud vertical)
- Recent conversation history (last 20 messages)
- Full OCR text of any documents you reference

Claude answers based on what's actually in the workspace — not general knowledge. If you ask "what properties did the nonprofit overpay for?" Claude reads your transactions table and gives you the specific answer with real numbers.

Every query is written to the audit log.

### 9.4 Evidence Integrity — How We Prove Nothing Was Tampered With

**Documents:**
- Hash is generated before OCR, before extraction, before naming — it captures the original file
- `original_filename` and `uploaded_at` cannot be changed after the record is created
- Source URL is recorded for any document fetched from an API

**All other data:**
- Nothing is hard-deleted. Ever. Deleted records get `is_deleted = true` and `deleted_at = timestamp`. The original record stays in the database permanently.
- Every edit to every record writes a before/after snapshot to audit_log

**The audit log itself:**
- A PostgreSQL trigger (code that lives inside the database) prevents any UPDATE or DELETE on audit_log rows
- This is enforced at the database level — even if an attacker got into the application code, they could not alter the audit log
- Covers: every upload, every extraction, every search, every AI query, every login and logout, every data change

---

## 10. What's NOT in Phase 1

These features are real requirements — they're just not in Phase 1. We build Phase 1 first, make sure it works, then build on it.

| Feature | Why it's deferred | Which phase |
|---------|------------------|-------------|
| Pulling data from IRS TEOS, Ohio SOS, county records automatically | Needs Phase 1 extraction pipeline working first | Phase 2 |
| Document type field schemas (990 XML, UCC, deed fields) | Separate sub-spec needed; too detailed for this spec | Sub-spec before Phase 2 |
| Visual network graph of entity connections | Phase 1 data model supports it; the visualization comes later | Phase 2 |
| AI-guided investigation checklist | Needs the workflow engine built on top of Phase 1 | Phase 2 |
| Insurance automation vertical | Phase 1 proves the IDP core; insurance uses the same foundation | Phase 3 |
| Generate referral packages (AG, IRS, FBI, FCA formats) | Phase 1 collects the evidence; Phase 3 formats it | Phase 3 |
| Team collaboration and user invites | Phase 1 supports multi-user data model; the invite flow comes later | Phase 3 |
| AWS deployment | Phase 4; containers make this straightforward when the time comes | Phase 4 |
| Vector/semantic search (pgvector) | PostgreSQL full-text search handles Phase 1; vectors add nuance later | Phase 2 |

---

## 11. Open Questions

These need answers before or during implementation — they're not blockers to starting, but they need to be decided.

1. **Extraction confidence threshold** — When Claude is less than 70% confident in an extraction, how does the UI show this? Options: (a) yellow highlight on the field, (b) a "needs review" badge on the document card, (c) a dedicated review queue. Decide during frontend implementation.

2. **Document type sub-spec** — Before Phase 2 begins, we need a dedicated spec that defines every document type (Form 990, UCC, deed, SOS filing, building permit, obituary, insurance form) with exact fields. The IRS TEOS XML format is confirmed as the preferred source for 990s — it has every field; ProPublica only has a summary.

3. **Insurance form schema** — When Vertical 2 starts, map the insurance contact's current form system and email workflow before building anything. Understand the exact fields on their forms before writing an extraction schema.

4. **Auth upgrade path** — Phase 1 uses JWT with hand-rolled auth (you'll build it from scratch, which is good for learning). Phase 3 team collaboration may need a managed auth service. Design the JWT system so it can be swapped out without rewriting every endpoint.

5. **Workspace labeling** — The backend always uses "workspace." The fraud vertical UI should show "Case." The insurance vertical UI should show "Project." This is a frontend configuration — the database doesn't change between verticals.

---

## Glossary

Terms you'll encounter while building this:

| Term | What it means |
|------|--------------|
| **UUID** | Universally Unique Identifier — a random ID like `a3f2b1c4-8e6d-...` that's globally unique |
| **Hash / SHA-256** | A mathematical fingerprint of a file. Same file = same hash. Changed file = different hash. |
| **JWT** | JSON Web Token — a signed token that proves who you are without sending your password |
| **OCR** | Optical Character Recognition — software that reads text from images and PDFs |
| **tsvector** | PostgreSQL's internal format for full-text search — breaks text into searchable tokens |
| **GIN index** | A type of database index optimized for full-text search and JSON |
| **JSONB** | PostgreSQL's binary JSON format — stores flexible data structures with fast search support |
| **Soft delete** | Marking a record as deleted without removing it from the database |
| **Audit log** | An append-only record of every action — nothing in it can be changed or removed |
| **Vertical** | A specific industry use case (fraud, insurance) built on top of the shared IDP platform |
| **Schema** | In this context: the definition of what fields to extract from a document type |
| **Extraction** | The process of pulling structured data out of an unstructured document |
| **NLP** | Natural Language Processing — understanding plain English queries |
| **FTS** | Full-Text Search — searching the content of documents by keywords |
| **Docker** | A tool that packages your app into a container so it runs the same everywhere |
| **REST API** | A standard way for the frontend to talk to the backend over HTTP |
| **FastAPI** | A Python framework for building REST APIs with automatic documentation |
| **Alembic** | A database migration tool for Python — tracks changes to your database schema over time |
| **Migration** | A script that updates the database structure (adds tables, changes columns) |
