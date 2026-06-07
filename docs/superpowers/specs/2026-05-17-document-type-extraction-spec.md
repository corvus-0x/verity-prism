# Document Type Extraction Spec
**Project:** Verity Prism IDP Platform
**Date:** 2026-05-17
**Status:** Approved — implement before Phase 2 begins
**Purpose:** Defines the extraction schema for every document type the platform handles. Each schema seeds the `document_schemas` table and drives the AI extraction pipeline.

---

## How to Read This Spec

Each document type section contains:
- **What it is** — plain English description
- **Primary source** — where to get it and in what format
- **Fields to extract** — every field Claude should pull out, with type and whether it's required
- **Extraction notes** — edge cases, OCR challenges, or format variations to handle

The `schema_fields` JSON from each section goes directly into the `document_schemas` table. The `extraction_prompt` is the system instruction sent to Claude when processing this document type.

---

## Document Type: DEED

**What it is:** A legal instrument conveying ownership of real property from one party to another. Recorded at the county recorder's office. The most important document type for the fraud vertical.

**Primary source:** County recorder's office — PDF (scanned or digital). Ohio counties: search by party name or address on the county recorder website.

**Key variations:** Warranty deed, quitclaim deed, survivorship deed, affidavit of correction, covenant of record, right-of-way deed.

**Fields to extract:**

```json
[
  {"name": "grantor_name", "type": "name", "required": true,
   "description": "Person or entity conveying the property (the seller/transferor)"},
  {"name": "grantee_name", "type": "name", "required": true,
   "description": "Person or entity receiving the property (the buyer/transferee)"},
  {"name": "consideration_amount", "type": "currency", "required": true,
   "description": "Dollar amount paid. '$0', 'No Consideration', or 'Exempt' counts as 0"},
  {"name": "consideration_notes", "type": "text", "required": false,
   "description": "Any qualifier: 'exempt', 'love and affection', 'no consideration', etc."},
  {"name": "deed_type", "type": "text", "required": false,
   "description": "General Warranty Deed, Quitclaim Deed, Survivorship Deed, etc."},
  {"name": "property_address", "type": "address", "required": false,
   "description": "Street address of the property being transferred"},
  {"name": "parcel_number", "type": "id_number", "required": false,
   "description": "County assessor parcel ID (e.g. M51-2-312-12-01-01-12300)"},
  {"name": "legal_description", "type": "text", "required": false,
   "description": "Full legal description of the property: lot, block, subdivision, township"},
  {"name": "instrument_number", "type": "id_number", "required": false,
   "description": "Recorder's instrument number (e.g. 202300004871)"},
  {"name": "recording_date", "type": "date", "required": true,
   "description": "Date the deed was officially recorded at the courthouse"},
  {"name": "execution_date", "type": "date", "required": false,
   "description": "Date the deed was signed (may differ from recording date)"},
  {"name": "preparing_attorney", "type": "name", "required": false,
   "description": "Attorney or firm who prepared the deed"},
  {"name": "notary_name", "type": "name", "required": false,
   "description": "Notary public who witnessed the signing"},
  {"name": "auditor_stamp_value", "type": "currency", "required": false,
   "description": "Value stamped by the county auditor — may differ from stated consideration"},
  {"name": "prior_instrument", "type": "id_number", "required": false,
   "description": "Reference to the prior deed (OR Vol/Page or prior instrument number)"},
  {"name": "title_search_note", "type": "text", "required": false,
   "description": "Any note that deed was prepared WITHOUT BENEFIT OF A TITLE SEARCH"}
]
```

**Extraction notes:**
- $0 considerations may be written as "$0", "No Consideration", "Exempt from conveyance fees", or "Love and affection." Normalize all to "0" in `consideration_amount`.
- The auditor stamps a value that may differ from stated consideration — extract both.
- "Prepared without benefit of a title search" is a red flag — always extract if present.
- Instrument numbers in Ohio are formatted as 9-digit numbers (e.g. 202300004871).

---

## Document Type: 990

**What it is:** IRS Form 990, the annual information return filed by 501(c)(3) tax-exempt organizations. The most data-rich document for the fraud vertical.

**Primary source:** IRS TEOS (Tax Exempt Organization Search) at apps.irs.gov/app/eos — **use XML format, not PDF.** TEOS XML has every line, every schedule, and every checkbox. ProPublica Nonprofit Explorer only has surface data and cannot return schedules. Always pull from TEOS.

**Key variations:** 990, 990-EZ, 990-N (postcard — minimal data), 990-PF (private foundations).

**Fields to extract:**

```json
[
  {"name": "organization_name", "type": "name", "required": true,
   "description": "Legal name of the filing organization"},
  {"name": "ein", "type": "id_number", "required": true,
   "description": "Employer Identification Number (9 digits, format: XX-XXXXXXX)"},
  {"name": "tax_year", "type": "text", "required": true,
   "description": "Tax year this return covers (e.g. 2023)"},
  {"name": "gross_receipts", "type": "currency", "required": true,
   "description": "Total gross receipts for the year (Part I Line 12 or equivalent)"},
  {"name": "total_revenue", "type": "currency", "required": false,
   "description": "Total revenue (may differ from gross receipts)"},
  {"name": "total_expenses", "type": "currency", "required": false,
   "description": "Total expenses for the year"},
  {"name": "net_assets_end", "type": "currency", "required": false,
   "description": "Net assets or fund balances at end of year"},
  {"name": "principal_officer_name", "type": "name", "required": true,
   "description": "Name of the principal officer (president, CEO, etc.)"},
  {"name": "principal_officer_compensation", "type": "currency", "required": false,
   "description": "Compensation reported for the principal officer"},
  {"name": "officer_hours_per_week", "type": "text", "required": false,
   "description": "Hours per week reported for the principal officer"},
  {"name": "board_member_count", "type": "text", "required": false,
   "description": "Number of voting board members"},
  {"name": "independent_board_members", "type": "text", "required": false,
   "description": "Number of independent (non-family, non-employed) board members"},
  {"name": "coi_policy", "type": "boolean", "required": true,
   "description": "Does the org have a written conflict of interest policy? (Part VI Line 12a)"},
  {"name": "whistleblower_policy", "type": "boolean", "required": true,
   "description": "Does the org have a written whistleblower policy? (Part VI Line 13)"},
  {"name": "financial_statements_audited", "type": "boolean", "required": true,
   "description": "Were financial statements audited by an independent accountant? (Part VI Line 15)"},
  {"name": "related_party_transactions_disclosed", "type": "boolean", "required": true,
   "description": "Part IV Line 28a/b/c — did org disclose related-party transactions?"},
  {"name": "schedule_l_filed", "type": "boolean", "required": false,
   "description": "Was Schedule L (Transactions with Interested Persons) attached?"},
  {"name": "program_service_revenue", "type": "currency", "required": false,
   "description": "Revenue from program service activities"},
  {"name": "contribution_revenue", "type": "currency", "required": false,
   "description": "Total contributions, gifts, grants received"},
  {"name": "unrelated_business_income", "type": "currency", "required": false,
   "description": "Unrelated business taxable income (if 990-T also filed)"},
  {"name": "number_of_employees", "type": "text", "required": false,
   "description": "Total number of employees reported"},
  {"name": "paid_preparer_name", "type": "name", "required": false,
   "description": "Name of the paid preparer who signed the return"},
  {"name": "paid_preparer_ptin", "type": "id_number", "required": false,
   "description": "Preparer Tax Identification Number (PTIN) of the paid preparer"},
  {"name": "paid_preparer_firm", "type": "name", "required": false,
   "description": "Name and address of the preparer's firm"}
]
```

**Extraction notes:**
- For TEOS XML: field values are in structured XML tags — extraction is more reliable than OCR on scanned PDFs.
- The governance fields (COI policy, whistleblower policy, audit) are Yes/No checkboxes — critical for fraud detection.
- `related_party_transactions_disclosed` being "No" after being "Yes" in a prior year is SR-025 FALSE_DISCLOSURE — always extract across all years to enable year-over-year comparison.
- `paid_preparer_ptin` is a unique identifier for the CPA — useful for finding if one preparer signs for multiple suspicious organizations.

---

## Document Type: 990-T

**What it is:** IRS Form 990-T, filed alongside a 990 when the organization has unrelated business taxable income (UBTI). A 990-T means the nonprofit is running commercial operations.

**Primary source:** IRS TEOS — same source as 990, filed as an attachment.

**Fields to extract:**

```json
[
  {"name": "organization_name", "type": "name", "required": true,
   "description": "Legal name of the filing organization"},
  {"name": "ein", "type": "id_number", "required": true,
   "description": "Employer Identification Number"},
  {"name": "tax_year", "type": "text", "required": true,
   "description": "Tax year this return covers"},
  {"name": "activity_code", "type": "id_number", "required": true,
   "description": "NAICS/activity code describing the unrelated business (e.g. 722513 = limited-service restaurants)"},
  {"name": "gross_unrelated_income", "type": "currency", "required": true,
   "description": "Gross income from unrelated trade or business"},
  {"name": "total_deductions", "type": "currency", "required": false,
   "description": "Total deductions from unrelated business income"},
  {"name": "unrelated_business_taxable_income", "type": "currency", "required": true,
   "description": "Net unrelated business taxable income after deductions"},
  {"name": "paid_preparer_name", "type": "name", "required": false,
   "description": "Name of the paid preparer"},
  {"name": "paid_preparer_ptin", "type": "id_number", "required": false,
   "description": "PTIN of the paid preparer"}
]
```

**Extraction notes:**
- Activity code 722513 (limited-service restaurants) is significant — confirms commercial food service operation.
- If a nonprofit files a 990-T, it's operating a business. Cross-reference with deed records to determine if that business is on LLC-owned land.

---

## Document Type: UCC

**What it is:** UCC Financing Statement (Form UCC-1) — a public filing that establishes a creditor's security interest in a debtor's collateral. Filed with the Secretary of State. UCC amendments (UCC-3) modify existing filings.

**Primary source:** Secretary of State UCC search — PDF from state portal.

**Fields to extract:**

```json
[
  {"name": "filing_number", "type": "id_number", "required": true,
   "description": "The SOS filing/document number (e.g. OH00186299054)"},
  {"name": "filing_type", "type": "text", "required": true,
   "description": "UCC1 (original), UCC3 (amendment), UCC3 continuation, UCC3 termination"},
  {"name": "filing_date", "type": "date", "required": true,
   "description": "Date the filing was made with the SOS"},
  {"name": "debtor_names", "type": "text", "required": true,
   "description": "All debtor names listed on this filing (may be multiple — list all)"},
  {"name": "debtor_addresses", "type": "address", "required": false,
   "description": "Addresses of all debtors listed"},
  {"name": "secured_party_name", "type": "name", "required": true,
   "description": "Name of the creditor holding the security interest"},
  {"name": "secured_party_address", "type": "address", "required": false,
   "description": "Address of the secured party"},
  {"name": "collateral_description", "type": "text", "required": true,
   "description": "Description of the collateral securing the debt"},
  {"name": "amends_filing_number", "type": "id_number", "required": false,
   "description": "If this is a UCC3, the original filing number being amended"},
  {"name": "continuation_expiration_date", "type": "date", "required": false,
   "description": "If this is a continuation, the new expiration date"}
]
```

**Extraction notes:**
- Multiple debtors on one filing are common — extract ALL names, comma-separated.
- UCC3 amendments filed within minutes of each other (SR-004 UCC_BURST) are flagged automatically — the `filing_date` including time is important.
- SBA EIDL liens appear as UCC filings with "U.S. Small Business Administration" as secured party — flag these.
- Example Lender, PCA as secured party is an agricultural lender — note connection to EIDL liens if both cover the same debtor.

---

## Document Type: SOS-FILING

**What it is:** Secretary of State corporate filings — articles of incorporation/organization, dissolution certificates, reinstatement documents, statements of continued existence, LLP registrations.

**Primary source:** Secretary of State — PDF from state portal. Ohio: Ohio SOS Business Search.

**Fields to extract:**

```json
[
  {"name": "entity_name", "type": "name", "required": true,
   "description": "Legal name of the entity being registered or modified"},
  {"name": "entity_type", "type": "text", "required": true,
   "description": "LLC, Inc., LLP, Ltd., Nonprofit Corporation, etc."},
  {"name": "filing_type", "type": "text", "required": true,
   "description": "Articles of Incorporation, Articles of Organization, Certificate of Dissolution, Reinstatement, Statement of Continued Existence, LLP Registration, etc."},
  {"name": "document_number", "type": "id_number", "required": true,
   "description": "SOS document number (e.g. 201923401328)"},
  {"name": "entity_number", "type": "id_number", "required": false,
   "description": "SOS entity number — permanent ID for this entity (e.g. 7654321)"},
  {"name": "filing_date", "type": "date", "required": true,
   "description": "Date the filing was made with the SOS"},
  {"name": "effective_date", "type": "date", "required": false,
   "description": "Effective date if different from filing date"},
  {"name": "organizer_name", "type": "name", "required": false,
   "description": "Name of the organizer (person who filed the formation documents)"},
  {"name": "statutory_agent_name", "type": "name", "required": false,
   "description": "Name of the registered/statutory agent"},
  {"name": "statutory_agent_address", "type": "address", "required": false,
   "description": "Address of the statutory agent"},
  {"name": "principal_address", "type": "address", "required": false,
   "description": "Principal office address of the entity"},
  {"name": "stated_purpose", "type": "text", "required": false,
   "description": "Stated business purpose — note if blank or absent"},
  {"name": "filing_attorney_firm", "type": "name", "required": false,
   "description": "Law firm that filed this document, if identified"},
  {"name": "signatory_name", "type": "name", "required": false,
   "description": "Name of the person who signed the filing"}
]
```

**Extraction notes:**
- A blank or absent `stated_purpose` is significant — note explicitly as "BLANK."
- Formation date vs. dissolution date comparisons reveal timing patterns (e.g. LLC dissolved day before a replacement was formed).
- The filing attorney/firm appearing across multiple entity filings (e.g. Hanes Law Group on all Bright Future filings) establishes a professional network connection.
- For reinstatement filings, note the gap between cancellation and reinstatement — any transactions during that gap may be legally questionable.

---

## Document Type: BUILDING-PERMIT

**What it is:** A building permit issued by a county or municipality authorizing construction, renovation, or demolition. Public record.

**Primary source:** County or municipal building department website — PDF or web record. Ohio counties vary; many are searchable online by address or permit number.

**Fields to extract:**

```json
[
  {"name": "permit_number", "type": "id_number", "required": true,
   "description": "Official permit number (e.g. 20251152)"},
  {"name": "permit_type", "type": "text", "required": true,
   "description": "New construction, remodel, addition, demolition, electrical, sign, etc."},
  {"name": "issue_date", "type": "date", "required": true,
   "description": "Date the permit was issued"},
  {"name": "property_address", "type": "address", "required": true,
   "description": "Address of the construction site"},
  {"name": "parcel_number", "type": "id_number", "required": false,
   "description": "County parcel number of the construction site"},
  {"name": "project_description", "type": "text", "required": true,
   "description": "Description of the permitted work (e.g. 'NEW SMOKER', 'NEW BANQUET HALL')"},
  {"name": "estimated_value", "type": "currency", "required": true,
   "description": "Declared construction value — compare against org revenue"},
  {"name": "contractor_name", "type": "name", "required": false,
   "description": "Name of the licensed contractor performing the work"},
  {"name": "owner_name", "type": "name", "required": false,
   "description": "Property owner name as listed on the permit"},
  {"name": "square_footage", "type": "text", "required": false,
   "description": "Square footage of the project if stated"},
  {"name": "completion_date", "type": "date", "required": false,
   "description": "Date the permit was closed or work was completed"}
]
```

**Extraction notes:**
- `estimated_value` vs. the organization's annual revenue is SR-026 CONSTRUCTION_OVERAGE if the permit value exceeds total revenue.
- The same contractor appearing across multiple properties (e.g. Fletcher Construction on all Bright Future properties) establishes a network connection.
- A permit on an address that's owned by a private LLC (not the organization) confirms charitable funds going to private property.

---

## Document Type: OBITUARY

**What it is:** A published death notice, typically from a funeral home website or local newspaper. Used to establish family relationships and organizational connections.

**Primary source:** Funeral home websites, local newspaper archives, Legacy.com.

**Fields to extract:**

```json
[
  {"name": "deceased_name", "type": "name", "required": true,
   "description": "Full name of the deceased"},
  {"name": "death_date", "type": "date", "required": true,
   "description": "Date of death"},
  {"name": "death_location", "type": "address", "required": false,
   "description": "City/location of death"},
  {"name": "birth_date", "type": "date", "required": false,
   "description": "Date of birth"},
  {"name": "spouse_name", "type": "name", "required": false,
   "description": "Name of surviving or predeceased spouse"},
  {"name": "survivors_listed", "type": "text", "required": false,
   "description": "All surviving family members listed with their relationship and location"},
  {"name": "preceded_in_death", "type": "text", "required": false,
   "description": "Family members who predeceased — may establish generation/branch"},
  {"name": "memorial_donation_destinations", "type": "text", "required": false,
   "description": "Organizations named as recipients of memorial donations — establishes organizational affiliations"},
  {"name": "employer_or_occupation", "type": "text", "required": false,
   "description": "Occupation or employer mentioned"},
  {"name": "residence_at_death", "type": "address", "required": false,
   "description": "City/township of residence at time of death"},
  {"name": "funeral_home", "type": "name", "required": false,
   "description": "Funeral home handling the arrangements"}
]
```

**Extraction notes:**
- `memorial_donation_destinations` is high-value — it reveals which organizations the deceased was connected to. A DBA name appearing here (e.g. "Bright Future Ministries" instead of "Bright Future Ministries Inc") may flag an unregistered DBA.
- `survivors_listed` should capture ALL names, relationships, and locations — this maps the family network.
- Cross-reference survivor locations against known addresses in the case (Lakeview, Cedar Grove, Westfield, etc.).
- `preceded_in_death` establishes which family members and branches are deceased — important for ruling out deceased signatories.

---

## Document Type: INSURANCE-FORM

**What it is:** Any insurance form — claim, application, policy, declaration page, or report. The primary document type for Vertical 2 (insurance automation).

**Primary source:** Direct upload, email attachment, or form submission. Formats vary widely by insurer and form type.

**Note:** Insurance form schemas must be customized per insurer and form type. This is a general schema for Phase 1. Before Vertical 2 begins, map the specific forms used by the insurance contact and create dedicated schemas for each form type.

**Fields to extract:**

```json
[
  {"name": "form_type", "type": "text", "required": true,
   "description": "Claim, Application, Policy Declaration, Renewal, Endorsement, etc."},
  {"name": "policy_number", "type": "id_number", "required": false,
   "description": "Insurance policy number"},
  {"name": "claim_number", "type": "id_number", "required": false,
   "description": "Claim number if this is a claim form"},
  {"name": "insured_name", "type": "name", "required": true,
   "description": "Name of the policyholder or insured party"},
  {"name": "insured_address", "type": "address", "required": false,
   "description": "Address of the insured"},
  {"name": "insured_phone", "type": "text", "required": false,
   "description": "Phone number of the insured"},
  {"name": "insured_email", "type": "text", "required": false,
   "description": "Email address of the insured"},
  {"name": "date_of_loss", "type": "date", "required": false,
   "description": "Date the loss or incident occurred (claims)"},
  {"name": "date_submitted", "type": "date", "required": false,
   "description": "Date the form was submitted"},
  {"name": "coverage_type", "type": "text", "required": false,
   "description": "Auto, home, health, commercial, life, etc."},
  {"name": "claim_amount", "type": "currency", "required": false,
   "description": "Dollar amount of the claim"},
  {"name": "description_of_loss", "type": "text", "required": false,
   "description": "Free-text description of what happened"},
  {"name": "agent_name", "type": "name", "required": false,
   "description": "Name of the insurance agent"},
  {"name": "agent_number", "type": "id_number", "required": false,
   "description": "Agent or producer license number"},
  {"name": "signature_present", "type": "boolean", "required": false,
   "description": "Does the form contain a signature?"},
  {"name": "missing_required_fields", "type": "text", "required": false,
   "description": "List any fields that appear required but are blank or missing"}
]
```

**Extraction notes:**
- `missing_required_fields` is the key value-add for the insurance vertical — catching incomplete forms before they enter downstream systems.
- Field names will need to be customized per insurer's specific form layout. Use this as the starting schema and extend it.

---

## Document Type: COURT-FILING

**What it is:** Any document filed in a court proceeding — complaint, motion, judgment, order, subpoena, lien, lis pendens.

**Primary source:** PACER (federal), state court e-filing portals, or county clerk of courts.

**Fields to extract:**

```json
[
  {"name": "court_name", "type": "name", "required": true,
   "description": "Name of the court where filed"},
  {"name": "case_number", "type": "id_number", "required": true,
   "description": "Court case number"},
  {"name": "filing_type", "type": "text", "required": true,
   "description": "Complaint, Motion, Order, Judgment, Lis Pendens, Subpoena, etc."},
  {"name": "filing_date", "type": "date", "required": true,
   "description": "Date filed with the court"},
  {"name": "plaintiff_name", "type": "name", "required": false,
   "description": "Plaintiff(s) — the party bringing the action"},
  {"name": "defendant_name", "type": "name", "required": false,
   "description": "Defendant(s) — the party being sued"},
  {"name": "subject_matter", "type": "text", "required": false,
   "description": "What the case is about"},
  {"name": "judgment_amount", "type": "currency", "required": false,
   "description": "Dollar amount of judgment if applicable"},
  {"name": "attorney_plaintiff", "type": "name", "required": false,
   "description": "Attorney representing the plaintiff"},
  {"name": "attorney_defendant", "type": "name", "required": false,
   "description": "Attorney representing the defendant"},
  {"name": "property_address", "type": "address", "required": false,
   "description": "Property address if this is a real estate action"}
]
```

---

## Document Type: CORRESPONDENCE

**What it is:** Letters, emails, memos, or any written communication between parties.

**Fields to extract:**

```json
[
  {"name": "sender_name", "type": "name", "required": false,
   "description": "Name of the sender"},
  {"name": "sender_organization", "type": "name", "required": false,
   "description": "Organization the sender represents"},
  {"name": "recipient_name", "type": "name", "required": false,
   "description": "Name of the recipient"},
  {"name": "recipient_organization", "type": "name", "required": false,
   "description": "Organization the recipient represents"},
  {"name": "date_sent", "type": "date", "required": false,
   "description": "Date the correspondence was sent"},
  {"name": "subject", "type": "text", "required": false,
   "description": "Subject line or topic of the correspondence"},
  {"name": "key_claims", "type": "text", "required": false,
   "description": "Main assertions, requests, or findings stated in the document"},
  {"name": "referenced_entities", "type": "text", "required": false,
   "description": "Organizations, properties, or people specifically referenced"}
]
```

---

## Document Type: NEWS-ARTICLE

**What it is:** Published news coverage relevant to the case — local newspaper, TV station website, investigative journalism.

**Fields to extract:**

```json
[
  {"name": "headline", "type": "text", "required": true,
   "description": "Article headline"},
  {"name": "publication_name", "type": "name", "required": true,
   "description": "Name of the publication or outlet"},
  {"name": "publication_date", "type": "date", "required": true,
   "description": "Date the article was published"},
  {"name": "author_name", "type": "name", "required": false,
   "description": "Byline author"},
  {"name": "people_mentioned", "type": "text", "required": false,
   "description": "All named individuals mentioned in the article"},
  {"name": "organizations_mentioned", "type": "text", "required": false,
   "description": "All organizations mentioned"},
  {"name": "key_facts_reported", "type": "text", "required": false,
   "description": "Key factual claims made in the article"},
  {"name": "article_url", "type": "text", "required": false,
   "description": "URL of the article if available"}
]
```

---

## Seeding the Database

These schemas seed the `document_schemas` table. Write a seed script at `backend/app/seeds/document_schemas.py` that inserts one row per document type defined above. Run it once after the initial migration.

The seed script should:
1. Check if schemas already exist before inserting (idempotent — safe to run multiple times)
2. Set `vertical = "fraud"` for DEED, 990, 990-T, UCC, SOS-FILING, BUILDING-PERMIT, OBITUARY
3. Set `vertical = "insurance"` for INSURANCE-FORM
4. Set `vertical = "general"` for COURT-FILING, CORRESPONDENCE, NEWS-ARTICLE
5. Set `is_active = True` for all
6. Set `version = 1` for all initial schemas

The `extraction_prompt` for each schema should be:
```
You are extracting structured data from a [DOCUMENT TYPE]. Extract every field listed in the schema. For each field:
- Return the exact value as it appears in the document
- If the field is not present or cannot be determined, return null
- For currency fields, return only the numeric value (e.g. "300000.00" not "$300,000")
- For date fields, return in YYYY-MM-DD format
- For boolean fields, return true or false
- Rate your confidence from 0.0 to 1.0 — be honest about uncertainty
```

---

## What This Enables

With these schemas seeded, every document uploaded to the platform will:
1. Be classified into one of these types automatically
2. Have every defined field extracted and stored in `document_extractions`
3. Be fully indexed for NLP search by both content and field values
4. Surface field-level confidence scores so low-quality extractions are flagged

The fraud vertical signal detection (SR-003, SR-005, SR-024, SR-025, etc.) can then run automatically against the structured extraction data rather than requiring manual review of raw documents.
