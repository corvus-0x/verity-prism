# Verity Prism

An intelligent document processing platform that refracts documents into every component they contain.

---

## What It Does

Verity Prism ingests documents in any format — PDFs, images, spreadsheets, XML — and automatically extracts every meaningful data point into structured, individually searchable fields. Every name, date, dollar amount, address, and ID number becomes its own record.

Search across everything in plain English. No SQL. No technical knowledge required.

Built to work across industries. The fraud investigation vertical is the proving ground. Insurance, legal, and compliance follow the same pattern.

## Status

**Planning phase complete. Build in progress.**

The architecture is designed. The database schema is defined. Implementation begins now.

Follow the build: [From Case to Code](https://corvus-0x.hashnode.dev)

## Stack

- **Backend** — Python, FastAPI, PostgreSQL
- **Frontend** — React, Vite, Tailwind CSS
- **AI** — Claude API (document extraction, NLP search, chat)
- **Infrastructure** — Docker, AWS

## Architecture

Five layers:

1. **Ingestion** — SHA-256 hash first (evidence lock), then store
2. **Extraction** — OCR → document type detection → AI field extraction → one row per field
3. **Knowledge base** — PostgreSQL with full-text search and field-level indexes
4. **Vertical logic** — fraud investigation features sit here, not in the core
5. **UI** — plain English search bar as the primary interface

## Documentation

- `docs/superpowers/specs/` — design specifications
- `docs/superpowers/plans/` — implementation plans
- `docs/blog/` — blog post drafts

---

*Built by [Corvus](https://corvus-0x.hashnode.dev)*
