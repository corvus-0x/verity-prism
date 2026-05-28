# Evals Learning Pathway

A practical progression from where you are now to production-grade evaluation systems.
Each stage builds on the previous one — don't skip ahead.

---

## Where You Are Now

You have working extraction evals in `backend/tests/evals/test_deed_extraction.py`.
They call real Claude, score 7 required fields across 3 deed cases, and run separately
from unit tests. That is Stage 1 complete.

---

## Stage 1 — Deterministic Field Scoring (done)

**What it is:** Ground truth cases with expected values. Score by exact or normalized match.

**What you built:**
- `CASES` list with realistic OCR text and `expected` dicts
- `score_field()` with date normalization, county suffix stripping, substring matching for entity names
- `pytest.mark.eval` separating these from unit tests

**The skill:** Writing test cases that are strict enough to catch real failures but
lenient enough not to fail on irrelevant formatting variation. The first run failing
on `recording_county` was exactly right — it revealed Claude's formatting behavior
and forced a deliberate decision about what "correct" means.

**Extend when:** You add new document types (SOS-FILING, OBITUARY) or change
extraction prompts. New schema → new eval file following the same pattern.

---

## Stage 2 — Coverage and Edge Cases

**What it is:** Expanding beyond happy-path cases to test extraction on hard inputs.

**What to build:**

```
backend/tests/evals/
    test_deed_extraction.py        ← you have this
    test_deed_edge_cases.py        ← add this next
    test_sos_extraction.py         ← when SOS schema matters
```

**Edge cases worth testing for deeds:**
- Minimal document — only the stamp block, no preparer, no notary
- Multi-grantor deed — "John Smith and Mary Smith, husband and wife"
- Correction deed — references a prior instrument number
- Deed with no property address (legal description only)
- Handwritten-OCR simulation — typos, broken line breaks, garbled numbers

**The skill:** Thinking adversarially about your extraction pipeline. If a fraud
investigator relies on `grantor_name` being correct, what document inputs would
make it wrong? Write those as test cases before they appear in production.

---

## Stage 3 — Regression Baseline

**What it is:** A score you track over time. When you change the extraction prompt,
you compare before vs. after.

**What to build:**

```python
# backend/tests/evals/run_baseline.py
# Run all evals and write results to a JSON file.

import json, subprocess, datetime

result = subprocess.run(
    ["pytest", "tests/evals/", "-m", "eval", "--tb=no", "-q", "--json-report",
     "--json-report-file=eval_results.json"],
    capture_output=True
)
# Parse eval_results.json, compute per-document-type pass rate, append to
# docs/evals/baseline_history.jsonl with a timestamp and git commit hash.
```

**The metric to track:**

```
DEED required fields pass rate: 21/21 (100%)  — commit abc1234  2026-05-28
```

**When it matters:** Before you touch the DEED extraction prompt or schema fields,
run baseline. After your change, run again. If pass rate drops, you broke something.
If it holds, you can ship with confidence.

**The skill:** Treating prompt changes like code changes — with before/after evidence,
not gut feel.

---

## Stage 4 — LLM-as-Judge for Freetext Fields

**What it is:** Using Claude to score fields that can't be exact-matched, like
`legal_description` and `subject_to_clause`.

Right now `legal_description` is scored as `non_null` — you only check it exists.
That's a weak assertion. A judge can check whether it's actually a legal description
and not garbage.

**What to build:**

```python
import anthropic

_judge_client = anthropic.Anthropic()

def judge_legal_description(actual: str) -> dict:
    """Ask Claude whether the extracted value looks like a valid legal description."""
    response = _judge_client.messages.create(
        model="claude-haiku-4-5",   # cheap — you'll call this many times
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": (
                f"Does this look like a valid real estate legal description? "
                f"Answer only: yes, no, or unsure. Then one sentence why.\n\n{actual}"
            )
        }]
    )
    text = response.content[0].text.strip().lower()
    return {
        "passed": text.startswith("yes"),
        "reasoning": text
    }
```

**Use Haiku for judges.** Each eval case calls the judge once per freetext field.
Haiku is 5× cheaper than Sonnet and fast enough for this. Never use Opus for judges —
you're running these in bulk.

**The skill:** Knowing when exact match is the right tool and when it isn't.
Instrument numbers, dates, and entity names are exact-match territory.
Legal descriptions, correspondence summaries, and resolution references are judge territory.

---

## Stage 5 — Eval Dataset Management

**What it is:** Treating eval cases as data you maintain, not code you write once.

Right now your cases are hardcoded in the test file. That works at 3 cases.
It breaks at 50.

**What to build:**

```
backend/tests/evals/
    fixtures/
        deed_cases.json          ← cases as structured data
        sos_cases.json
    test_deed_extraction.py      ← loads from fixtures/, no hardcoded cases
```

```json
// deed_cases.json
[
  {
    "id": "warranty_residential",
    "description": "Standard residential warranty deed",
    "ocr_text": "...",
    "expected": {
      "instrument_number": "202308140045",
      "recording_date": "2023-08-14",
      ...
    }
  }
]
```

**Why this matters:** When you onboard real case documents from your fraud investigation
vertical, you'll want to add eval cases by writing JSON, not editing Python. Non-engineers
(future collaborators, domain experts) can contribute cases without touching test code.

**The skill:** Separating test logic (how to score) from test data (what to score against).
This is the same separation as schema-driven extraction — data drives behavior.

---

## Stage 6 — Continuous Evals in CI

**What it is:** Running a subset of evals automatically on every PR.

You can't run all evals in CI — they cost money and are slow. But you can run a
**smoke subset**: one case per document type, the simplest one.

```yaml
# In your GitHub Actions or CI config:
- name: Extraction smoke evals
  run: |
    pytest tests/evals/ -m "eval and smoke" --tb=short
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
    TEST_DATABASE_URL: ${{ secrets.TEST_DATABASE_URL }}
```

Mark your simplest case per type as `@pytest.mark.smoke`:

```python
@pytest.mark.eval
@pytest.mark.smoke   # ← runs in CI
@pytest.mark.parametrize("case", CASES[:1], ...)
def test_deed_required_fields_smoke(case, deed_schema):
    ...
```

**The skill:** Triaging what needs to run always vs. what runs on-demand.
Smoke evals catch regressions from prompt or schema changes before they hit production.
Full evals run before a release or after a major prompt rewrite.

---

## What to Read

These are ordered by relevance to where you are, not by prestige:

1. **Anthropic's Eval Cookbook** — practical, shows the same patterns you built
   `https://docs.anthropic.com/en/docs/test-and-evaluate/eval-techniques`

2. **HELM (Holistic Evaluation of Language Models)** — Stanford's benchmark framework.
   You won't use it directly, but understanding how they structure evaluation tasks
   will inform how you think about your own.
   `https://crfm.stanford.edu/helm/`

3. **LangSmith Docs** — if you ever add a LangChain layer, this is how tracing and
   evals work in that ecosystem. The concepts (dataset, run, feedback) translate
   even if you don't use the product.

4. **"Evaluating LLMs is Harder Than it Looks"** — Shankar et al. (2024).
   Good paper on why human-written ground truth degrades over time and what to do about it.

---

## The Thing That Actually Matters

The cases you write are more valuable than the infrastructure you build around them.
A good eval case is:

- **Grounded in a real failure mode** — not just a happy path. If a fraud investigator
  would be misled by a wrong extraction, that scenario is worth a test case.
- **Specific enough to fail** — "non_null" is a weak assertion. Know what the correct
  value is.
- **Stable** — the expected value shouldn't change unless the schema changes.

Write one new case every time you find a document in production where the extraction
was wrong. That's how the eval suite earns its keep.
