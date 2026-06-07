# Job Description Analysis — Verity Prism Build Alignment

**Date:** 2026-06-01  
**Purpose:** Working document. Nine job descriptions mapped against Verity Prism to identify skill gaps, decide what to build next, and ensure Phase B additions serve both the product and the portfolio.

---

## Why I Did This

Verity Prism was built entirely from the investigation use case outward. Every decision — the row-per-field extraction table, the vertical cap architecture, the FTS search layer, the agentic tool dispatch loop — came from what that specific problem needed. The risk of building that way is isolation: you solve the right problems but don't know what the market calls them, and you miss gaps you don't know to look for.

At the point where the engine was complete and Phase 3 (vertical packaging) was the obvious next step, I stopped and read nine AI engineering job descriptions against the platform. The goal wasn't to pivot — it was to find out where I was on the map before building further. The exercise shaped what Phase B became.

---

## The Nine JDs

### 1. Nephew — AI Engineer
**Compensation:** $100k–$180k + equity  
**Location:** Remote  
**Company:** SMS-based chief-of-staff for small business owners

**What they want:**
- Agent runtime engineering — turning natural language into real actions that check their own work
- Writing "skills" — composable behaviors that teach the agent new shapes of work
- Eval and observability layer — catching regressions before users feel them
- Integrations — auth flows, webhook plumbing, schema mapping
- LangSmith for evals and observability (named explicitly)
- Pipedream for integrations
- Python + TypeScript
- Production trace reading — "follow a long thread of skill calls and memory writes"
- Self-checking agents

**Where Verity Prism matches:**
- Agent runtime: `ai_engine.py` — native Anthropic tool-use loop, 10-round cap, synthesis pass ✅
- Composable skills: `agent_tools.py` — 7 tools, vertical registry, runtime dispatch ✅
- Observability: `claude_call_logs`, confidence scoring, automation rate dashboard ✅
- Agent self-checking: extraction evaluator + retry loop ✅
- Python + TypeScript: backend is Python, frontend is React/TypeScript ✅

**Gaps:**
- LangSmith — named explicitly. I have the equivalent (`claude_call_logs`) but not the tool itself
- Pipedream — I have a custom connector framework, which is the same idea but not the same tool
- Formal eval datasets — I have confidence scoring, not dataset-driven evals

**Assessment:** Strong conceptual fit. The vocabulary gap (LangSmith) is the main issue. The evaluation skill they want — "built the eval and observability layer" — I have, but can't reference by name.

---

### 2. Kalmus Labs — Backend/AI Engineer (Core Team)
**Compensation:** 3% equity only (pre-seed)  
**Location:** Remote  
**Company:** Remora — AI-powered learning platform, documents into interactive experiences

**What they want:**
- LLM pipelines — RAG, embeddings, retrieval, prompt orchestration
- Multi-document search and contextual memory systems
- Document intelligence
- Agent behavior
- Backend architecture: Python, FastAPI, PostgreSQL, Redis, Docker
- Vector search: PGVector, Pinecone
- LangChain, LlamaIndex, OpenAI, Anthropic

**Where Verity Prism matches:**
- FastAPI + PostgreSQL + Docker: direct match ✅
- Document intelligence: literally what the platform is ✅
- Anthropic API: deep match ✅
- Agent behavior: tool-use loop ✅
- Observability: partial match ✅

**Gaps:**
- RAG/embeddings — Prism uses FTS, not vector embeddings. Significant gap — this is the vocabulary the market speaks
- Redis — not in stack
- PGVector/Pinecone — no vector search at all at this point
- LangChain/LlamaIndex — I built native, which is stronger engineering but not the keyword

**Applied for:** Yes (equity only, for the experience and resume value, not for the pay)

**Assessment:** Strong conceptual fit, significant vocabulary gap on vector search. PGVector is the direct fix. The equity-only structure means this is resume/experience value, not career trajectory.

---

### 3. Crosstie Tech — AI Solutions Engineer
**Compensation:** $80k–$120k + 0.05–0.1% equity  
**Location:** Remote (US)  
**Company:** AI-powered workflow automation for property and casualty insurance

**What they want:**
- Not a developer role — at the intersection of engineering, product, and customer workflows
- Configure AI-based applications for customer needs
- Debug integrations with customer technical teams
- Prompt engineering + generative AI systems
- SQL + API integrations + data formats
- Debug distributed systems
- Project management / customer implementation management
- Insurance domain (carriers, TPAs, adjusters, claims)

**Where Verity Prism matches:**
- FastAPI + Python: ✅
- Document intelligence for insurance: directly relevant ✅
- Prompt engineering: extraction prompts, model routing ✅
- API design + data formats (CSV/JSON export): ✅
- Async pipeline + debugging: ✅
- Insurance vertical (Vertical 2): the platform is being built for this domain ✅

**Gaps:**
- "Solutions engineer" is 50% customer-facing project management — hard to demonstrate from a solo build project
- Insurance domain vocabulary — didn't have this when I interviewed
- 2+ years professional experience — the customer implementation side is thinner

**Notes:** Had a first interview before Verity Prism existed. Lost at the domain vocabulary and customer-facing experience gap. Building the insurance vertical would have made that conversation different. The interviewer needed someone who knew what TPAs and adjusters actually do — not just the engineering.

**Assessment:** Good fit for the engineering half, weaker on the solutions/PM half. The insurance vertical (Phase 3B) directly addresses the domain gap.

---

### 4. Junior Software Engineer (Unnamed Client via Urrly)
**Compensation:** $85k–$115k  
**Location:** Remote-friendly, Austin TX preferred  
**Company:** Public safety software (sensitive criminal justice information)

**What they want:**
- Recent grad / bootcamp / 1 year experience
- Built full apps using AI coding agents
- Can demo real work during Zoom — can explain how their app works live
- React, Python web frameworks
- MVC-comparable architecture
- Database + API literacy
- Claude Code specifically mentioned as an acceptable tool
- AI-assisted development as daily workflow

**Where Verity Prism matches:**
- React + FastAPI (Python): direct match ✅
- Full-stack from scratch: ✅
- Claude Code as development workflow: literally how this was built ✅
- Database + API: PostgreSQL, SQLAlchemy, 16 routers ✅
- MVC-comparable: thin routers → services → models ✅
- Public safety domain: fraud vertical serves AG, IRS, FBI referrals ✅
- Immutable audit log + SHA-256 evidence lock: directly relevant to compliance requirements ✅

**Gaps:**
- Can demo real work: the engine hadn't been driven with a real case yet — this was the missing piece
- GitHub Actions CI/CD: listed as nice-to-have across similar roles

**Assessment:** The strongest domain match in the set. The platform was built for criminal justice investigation — evidence chain, immutable audit log, AG/FBI/IRS referral package. The one gap that matters is the demo. Can't walk someone through the platform in a Zoom if you've never run a real case through it. This is what prompted the engine validation run.

---

### 5. Swivl — AI Product Engineer (Claude Code)
**Compensation:** $70k–$150k + equity  
**Location:** Remote (US)  
**Company:** Self-storage automation — web, SMS, and voice AI agents

**What they want:**
- Claude Code as a core part of the development workflow
- Structured prompt engineering
- Documentation: plan files, PR descriptions, decision records
- Build features with LLMs as an integrated development tool
- Review and improve LLM-generated code
- TypeScript + Python
- Multi-agent system design awareness
- "Agentic coding has to already be how you work"

**Where Verity Prism matches:**
- Claude Code as daily workflow: this is literally how the platform is built ✅
- CLAUDE.md as structured prompting: the vertical separation, architecture constraints, docstring conventions ✅
- Specs in `docs/superpowers/specs/`: 9 spec files ✅
- PR descriptions with context and decisions: all PRs have structured descriptions ✅
- ADRs in `docs/decisions/`: architectural decision records ✅
- Python + TypeScript: ✅
- Multi-agent: `agent_registry.py`, vertical tool routing ✅

**Easter egg:** Job description ends with "check out our mascot Hoover the owl. What are his colors?" — a filter for candidates who actually read it. Answer: orange and brown.

**Assessment:** Strongest keyword match of all nine. The job title is "AI Product Engineer (Claude Code)" and Claude Code is how the entire platform was built. The interview story is: the workflow they're hiring for is the workflow I used to build Verity Prism. The gap is visibility — they can't see this without reading the repository and the commit history.

---

### 6. Upstart — Software Engineer II, Backend (AI Agents)
**Compensation:** $117k–$162k  
**Location:** Remote (US)  
**Company:** AI lending marketplace — loan servicing platform

**What they want:**
- 1.5+ years software engineering experience
- React or Vue + Python or Kotlin APIs
- Multi-component system design
- Metrics + monitoring + on-call support
- Loan servicing workflows, collections, borrower management

**Where Verity Prism matches:**
- Python + React: ✅
- API design: 16 routers ✅
- Testing: 222 tests, TDD ✅
- Multi-component system: full pipeline ✅

**Gaps:**
- Bachelor's degree — listed as minimum qualification. IBM cert is the "equivalent" argument but Upstart's HR pipeline is automated
- Loan servicing domain — completely different from what the platform does
- Ruby/Rails preferred — not in stack
- "At scale" — Prism is single-tenant
- On-call experience — solo developer, no on-call

**Assessment:** Weakest fit of the nine. Technology foundation is there but degree filter, domain mismatch, and Ruby preference make this unlikely to get through screening. Applied, but lowest priority for energy.

---

### 7. Iovance Biotherapeutics — AI Full-Stack Product Engineer
**Compensation:** Market rate (pharmaceutical)  
**Location:** Remote + Philadelphia occasionally  
**Company:** Cell therapy company — building internal AI tools for Commercial, Regulatory, Quality, Manufacturing, R&D

**What they want:**
- React + Node.js or Python full stack
- LLM API experience (Anthropic or OpenAI, named)
- Claude Code as daily workflow (named)
- Agentic AI frameworks + MCP (Model Context Protocol) mentioned as preferred
- Build micro-applications and workflow automations
- Work with non-technical stakeholders, demo to executives
- Rapidly prototype and ship
- "The multiplier is AI fluency"

**Where Verity Prism matches:**
- React + Python: ✅
- Anthropic API: deep match ✅
- Claude Code as workflow: ✅
- Agentic framework: `ai_engine.py`, tool-use loop ✅
- MCP: I use MCP servers daily (GitHub, Playwright, Railway, Windows) ✅
- Document workflows: the platform processes regulatory-type documents ✅
- Pharma alignment: Regulatory, Quality, Manufacturing all run on documents — same IDP problem Prism solves
- Customer-facing: entire prior career was customer-facing ✅
- 21 CFR Part 11 compliance relevance: immutable audit log, evidence chain ✅

**Gaps:**
- 2+ years professional experience — stated requirement, "equivalent practical experience" offered as alternative
- Node.js — Python is the alternative they accept
- Data visualization dashboards — partial (confidence scoring, automation rate)

**Assessment:** Top-3 fit. The MCP + Claude Code + Anthropic API depth is genuinely rare. Pharma's document-heavy compliance workflows are the same problem Prism solves in a different domain. Customer-facing background directly addresses the "demo to executives" requirement.

---

### 8. Stability AI — Junior Software Engineer
**Compensation:** Market rate  
**Location:** Remote (US or Canada)  
**Company:** AI company (Stable Diffusion, etc.) — internal engineering tooling

**What they want:**
- BS in CS with 2+ years experience, or MS with internship
- Python proficiency + production-ready code
- Strong debugging
- Generative AI experience (strong plus)
- Building scalable tools for engineering teams

**Where Verity Prism matches:**
- Python: ✅
- Generative AI: strong match — Anthropic API, extraction pipeline, AI chat ✅
- Well-tested code: 222 tests, TDD ✅
- Strong debugging: code audit remediation ✅

**Gaps:**
- Degree + 2 years industry experience: the primary filter
- Stability is a high-profile company with competitive applicant pool
- Tooling focus: they want internal developer tooling, not product engineering

**Assessment:** Reasonable to apply, realistic about the degree filter. Generative AI alignment is genuine. If it gets to a human who prioritizes what was built over where they studied, there's a conversation. At their volume, that's the variable.

---

### 9. Affirm — Software Engineer II, Backend (AI Agents)
**Compensation:** $125k–$175k  
**Location:** Remote Canada only  
**Company:** Buy Now Pay Later — AI agents for loan servicing

**What they want:**
- 1.5+ years software engineering
- React + Python or Kotlin APIs
- AI agents / omnichannel AI integration
- Multi-component system design
- Metrics + monitoring + on-call

**Where Verity Prism matches:**
- Python + React: ✅
- AI agents: deep match ✅
- API design + testing: ✅
- Multi-component system: ✅

**Hard blocker:** Remote Canada only. No US hiring for this role.

**Assessment:** Strong technical fit, geography kills it. Good reference point for what mid-level AI agent engineering looks like at a mature company.

---

## Consolidated Gap Analysis

Across nine JDs, these gaps appeared most consistently:

| Gap | JDs affected | Priority |
|---|---|---|
| Vector search / PGVector / RAG | Kalmus, Remora, Affirm, general AI roles | HIGH |
| LangSmith (or equivalent observability tool) | Nephew explicitly + implied across others | HIGH |
| GitHub Actions CI/CD | Public safety, Stability, Swivl implied | HIGH — half a day |
| Live demo capability | Public safety, Swivl, Iovance | HIGH — engine validation run |
| Formal eval datasets | Nephew, general AI | MEDIUM |
| AWS deployment | Multiple mid-level roles | MEDIUM (Phase 4B) |
| Redis | Kalmus, some others | LOW |
| Node.js | Some roles | LOW — Python is accepted alternative |

**Consistent strengths across all nine:**

- Anthropic/Claude API depth — rare, explicit strength at Iovance and Swivl
- Claude Code as development workflow — named at Swivl, implied at Iovance
- MCP usage — named at Iovance as preferred
- Python + React full stack — matched everywhere it mattered
- Document intelligence domain — directly matches 4 of the 9
- Testing discipline (222 tests, TDD, CodeRabbit) — visible on the repo
- Security/compliance patterns — relevant for public safety, pharma, fintech

---

## Decisions Made

**Decision 1: Additive, not rebuild**

The most important decision: don't replace the FTS search layer with pure vector search. FTS with field-level filters is more accurate for the structured queries the investigation use case runs. Signal detection depends on it. Replacing it would make the platform weaker, not just more legible.

Add PGVector alongside FTS. Run both. Route to the right mechanism per query. This is hybrid search — which turns out to be the production pattern at Elasticsearch, Pinecone, and every mature search infrastructure. The "from scratch" build accidentally landed on the right architecture. Adding the vector layer completes it.

**Decision 2: LangSmith wraps the existing client**

`claude_call_logs` is the billing/metering data source — can't replace it. LangSmith adds a debugging and tracing surface the call log doesn't have. Wrapping the Anthropic singleton is one line, transparent to all callers. Both coexist.

**Decision 3: Run the real case before adding anything**

The engine had never been driven with real documents. Without a baseline automation rate, every calibration decision is guesswork. The validation run is the prerequisite — it establishes what "the engine working" actually looks like, and it's the demo material the public safety and Swivl interviews require.

**Decision 4: Output format normalization is a prerequisite, not a nice-to-have**

Not explicitly in any JD, but surfaces during the validation run: currency stored as `$1,250,000.00` breaks every numeric signal comparison. Signal detection can't work without it. Built as Phase B-1, before LangSmith and PGVector.

**Decision 5: Skip Redis and Node.js**

Redis appeared in 2 of 9 JDs. Node.js appeared in 3. Neither is load-bearing for the roles that are the best fits (public safety, Swivl, Iovance all accept Python). Adding either without a real use case produces a toy demo, not a resume item. The platform already has a use case for LangSmith and PGVector. Redis and Node.js don't have one yet.

**Decision 6: CI/CD verification is a half-day, not a build**

GitHub Actions already existed in the repo. It had never been verified against live secrets. The "gap" here is documentation and confirmation, not engineering. Fast close.

---

## What Was Actually Built (Phase A + B)

| Built | Closes gap | Notes |
|---|---|---|
| CI/CD verification + secrets docs | GitHub Actions across 4+ JDs | Half a day — workflow already existed |
| Engine validation script (`validate_engine.py`) | Demo capability for 3 JDs | Also established the baseline needed for all future tuning |
| Absent-field evaluator fix | Not a gap — discovered during validation | 48% → 57% automation rate; the platform was measuring the wrong thing |
| Output format normalization | Eval/precision across multiple JDs | Prerequisite for signal detection |
| LangSmith integration | Nephew explicitly; implied elsewhere | Wraps existing singleton, call log stays |
| PGVector + embedding service + hybrid search | RAG/vector search across 3 JDs | Hybrid is the right architecture — not a compromise |
| UI fixes (401 loop, multi-upload, page controls, overview links, sidebar upload) | Indirectly — demo capability | Discovered during validation run; platform had to be demoable |

**What wasn't built:**
- Redis: no real use case yet
- Node.js: Python is accepted everywhere that matters
- Formal eval datasets: future work — would pair with LangSmith traces
- AWS deployment: Phase 4B

---

## What This Document Is For

When someone in an interview asks "how did you decide what to build?" — this is the answer. The platform wasn't built to check resume boxes. It was built to solve a real investigation problem. The JD analysis was a calibration exercise: given where the engine stands, what additions would make the most difference for both the product and the portfolio simultaneously? The answer was always: add things that have a real use case in the investigation first, and happen to close market vocabulary gaps second.

That's why PGVector went in as hybrid search and not as a replacement. That's why LangSmith wraps the existing client instead of replacing the call log. That's why Redis didn't make the list. The investigation use case is the filter. Everything else follows from that.

---

*This document covers the analysis session from 2026-06-01. Phase A + B merged as PR #15 on 2026-06-01.*
