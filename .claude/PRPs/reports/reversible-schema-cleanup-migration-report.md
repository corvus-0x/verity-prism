# Implementation Report: Reversible Schema-Cleanup Migration (c8dd75f9d15c)

## Summary
Rewrote `c8dd75f9d15c.downgrade()` to deterministically restore the affected general
`document_schemas` (OBITUARY vertical, 3 extraction_prompts, 5 field descriptions) to their
canonical pre-cleanup seed values, recovered verbatim from git revision `6f655fa^` and embedded
as module constants. `upgrade()` left byte-for-byte unchanged. Added an isolated round-trip
reversibility test.

## Assessment vs Reality
| Metric | Predicted (Plan) | Actual |
|---|---|---|
| Complexity | Small–Medium | Medium (test approach harder than planned) |
| Confidence | (n/a, post-review) | Implemented in one session |
| Files Changed | 2 | 2 |

## Tasks Completed
| # | Task | Status | Notes |
|---|---|---|---|
| 1 | Recover canonical originals, embed constants | Complete | SR-0 count verified 5==5; all 3 prompts verbatim-match git |
| 2 | Rewrite downgrade() to restore canonical values | Complete | upgrade() unchanged; guarded UPDATEs |
| 3 | Round-trip reversibility test | Complete — **deviated** | See Deviations |

## Validation Results
| Level | Status | Notes |
|---|---|---|
| Static (ruff) | Pass | clean on both files |
| Unit/Integration test | Pass | isolated round-trip test |
| Full suite | Pass | 328 passed, no regressions |

## Files Changed
| File | Action | Lines |
|---|---|---|
| `backend/alembic/versions/c8dd75f9d15c_*.py` | UPDATED | +220 / -8 |
| `backend/tests/test_migration_c8dd75f9d15c.py` | CREATED | +~115 |

## Deviations from Plan
**Test isolation strategy changed (Task 3).** The plan drove the round-trip via
`command.downgrade(cfg, "d4e9f2a83b17")` then `command.upgrade(cfg, "head")`. Running it proved
this unsafe: unwinding the whole chain from head executes every intervening migration's downgrade,
and `e1ca59dae292`'s downgrade is incomplete (orphans the `proposal_type` enum), so the re-upgrade
fails with `type "proposal_type" already exists` — unrelated to c8dd, and it corrupted the test DB.

**Corrected approach:** the test now binds the migration's global `op` to an `Operations` context
on a single connection and calls c8dd's own `upgrade()`/`downgrade()` inside a transaction that is
rolled back. Fully isolated, fast (~1s), touches no other migration.

## Issues Encountered / Discovered
1. **Verifier encoding bug (resolved):** initial constant-vs-git check reported false MISMATCH due
   to `subprocess(text=True)` decoding git output as Windows cp1252 vs utf-8 file read (em-dash).
   Fixed the harness (decode bytes as utf-8); constants confirmed verbatim.
2. **Pre-existing latent bug (OUT OF SCOPE — flagged for decision):**
   `e1ca59dae292.downgrade()` drops the `schema_change_proposals` table but NOT its `proposal_type`
   enum, so a down→up round-trip of that migration fails. Not fixed here (different migration,
   different plan). Recommend a separate fix adding `DROP TYPE IF EXISTS proposal_type` to that
   downgrade.

## Tests Written
| Test File | Tests | Coverage |
|---|---|---|
| `tests/test_migration_c8dd75f9d15c.py` | 1 | vertical + extraction_prompt + schema_fields description round-trip |

## Next Steps
- [ ] Code review (`/code-review`) of the diff
- [ ] Commit (`/prp-commit`) + PR (`/prp-pr`) on `feat/reversible-schema-cleanup-downgrade`
- [ ] Separate ticket: fix `e1ca59dae292` downgrade enum orphan
