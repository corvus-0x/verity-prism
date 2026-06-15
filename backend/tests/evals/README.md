# Brief Eval Harness

Measures `synthesize_brief` quality on **faithfulness** (claim precision) and
**completeness** (salience recall) over hand-authored golden fixtures.

## Run

```bash
docker-compose run --rm \
  -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  backend pytest tests/evals/test_brief_quality.py -v -m eval
```

Real Claude (synthesis + temp-0 judge); excluded from CI. Writes a scorecard to
`results/brief_eval.json` (gitignored).

## Hybrid gate
- **Hard asserts:** every claim cites a real evidence id; clean fixtures invent
  no claims; every planted salience is detected by the engine.
- **Measured (loose floors):** faithfulness >= 0.70, completeness >= 0.60.

## Sample scorecard
```text
── outlier_dupe_contradiction ──
  claims=5  faithfulness=1.00  completeness(brief)=0.80  completeness(engine)=1.00
── chronology_missing_field ──
  claims=2  faithfulness=1.00  completeness(brief)=1.00  completeness(engine)=1.00
── multi_doc_clean ──
  claims=0  faithfulness=1.00  completeness(brief)=1.00  completeness(engine)=1.00
── single_doc_minimal ──
  claims=0  faithfulness=1.00  completeness(brief)=1.00  completeness(engine)=1.00
```
(Illustrative — actual judge scores vary per run.)

## Pure unit tests (CI)
The seeder, fixtures, scorers, and judge JSON-parsing have ordinary unit tests
under `backend/tests/test_brief_*.py` and `test_golden_briefs.py` that run in CI
(no Claude). Only this runner needs a live key.
