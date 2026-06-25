# Plan: Make Schema-Cleanup Migration `c8dd75f9d15c` Downgrade Restore Canonical Pre-Cleanup Values

> **Revised after code review.** The original snapshot-in-`upgrade()` design was withdrawn:
> c8dd is committed to `main` and was applied on 2026-05-26 (`build-inventory.md:490`), so a
> snapshot added to `upgrade()` would never run on already-migrated databases. Editing
> `upgrade()` of a shipped migration is wrong; editing its **downgrade()** is correct, because
> already-upgraded DBs execute the *current file's* `downgrade()` code when rolling back.

## Summary
`c8dd75f9d15c.downgrade()` currently restores only `OBITUARY.vertical`; the extraction-prompt
and field-description edits are permanent. This plan rewrites `downgrade()` to deterministically
restore the **canonical pre-cleanup seed values** for exactly the surfaces `upgrade()` changed,
using original strings recovered from git history. `upgrade()` is left untouched.

## Repo Policy Justification (editing a shipped migration)
The general Alembic norm is "never edit a migration that has shipped." This plan takes a
**narrow, deliberate exception: `upgrade()` is NOT touched — only `downgrade()` is edited.**
Why this specific exception is safe:
- Any DB at or past c8dd already ran `upgrade()`; leaving it byte-for-byte unchanged means
  no forward-schema drift and no DB sees a different applied state.
- `downgrade()` is executed *only on rollback*, and an already-migrated DB runs the **current
  file's** `downgrade()` at that moment — so fixing it here is the only way to repair rollback
  behavior on those DBs. A new forward migration cannot alter c8dd's downgrade.
- `CLAUDE.md` has no rule forbidding migration edits; it requires this change land via a
  reviewed PR on a `feat/` branch (not a docs-only direct-to-main commit), which this will.
Editing `upgrade()` of a shipped migration would be the unsafe case and is explicitly excluded.

## Scope Caveat (explicit, per review)
This restores to the **known pre-c8dd canonical seed state** — NOT a guaranteed per-database
"exact prior state." Without a snapshot captured at upgrade time (which does not exist on
already-migrated DBs), arbitrary per-DB restoration is mathematically unavailable: a DB that
manually edited `document_schemas` after c8dd ran cannot be perfectly reconstructed. The best
achievable, and the goal here, is deterministic restoration to the canonical reference-data values.

## User Story
As an operator rolling back past c8dd, I want `alembic downgrade d4e9f2a83b17` to restore the
general schemas to their known pre-cleanup reference state, so a rollback yields a coherent,
expected `document_schemas` rather than half-cleaned data.

## Problem → Solution
Partial, lossy downgrade → Deterministic restore of the changed surfaces to canonical pre-c8dd
seed values, recovered from git and embedded as migration constants.

## Metadata
- **Complexity**: Small–Medium (verbose constants, simple logic)
- **Source PRD**: N/A
- **Estimated Files**: 2 (1 migration edited, 1 test created)

---

## UX Design
N/A — internal reference-data change. No API/UI surface.

---

## Mandatory Reading

| Priority | File / ref | Lines | Why |
|---|---|---|---|
| P0 | `backend/alembic/versions/c8dd75f9d15c_schema_cleanup_obituary_and_sr_.py` | 24-136 | The migration. `upgrade()` (24-125) defines the EXACT set of (type, column, field) surfaces to restore. Do not restore anything outside this set. |
| P0 | git `6f655fa` diff on `app/seeds/document_schemas.py` | full | The cleanup that produced the cleaned values. The `-` (red) lines ARE the canonical originals to restore to. Pull full prompt blobs via `git show 6f655fa^:backend/app/seeds/document_schemas.py`. |
| P0 | `backend/tests/conftest.py` | 30-31, 43-56, 60-63 | Migrations run via `command.upgrade(cfg,"head")`; `setup_db` TRUNCATES `document_schemas` before every test (so the test must create its own controlled rows); `test_engine` fixture for raw SQL. |
| P1 | `backend/alembic/versions/f2b3c4d5e6f7_seed_signal_types.py` | 28-115 | Archetype: inline seed constants + a downgrade that mechanically reverses upgrade. Mirror the inline-constant style. |
| P1 | `backend/alembic/versions/d4e9f2a83b17_*.py` | 64-80 | `down_revision`; idempotent-guard convention for downgrades. |

## External Documentation
No external research needed — internal patterns only.

---

## Patterns to Mirror

### INLINE_SEED_CONSTANTS
// SOURCE: backend/alembic/versions/f2b3c4d5e6f7_seed_signal_types.py:28-85
```python
SIGNAL_TYPES_SEED = [ {...}, {...} ]   # module-level data the migration owns
```
Embed the canonical originals as module-level constants in c8dd (e.g. `_ORIGINAL_DESCRIPTIONS`,
`_ORIGINAL_PROMPTS`) so `downgrade()` reads from one obvious place.

### RAW_SQL_EXECUTE
// SOURCE: backend/alembic/versions/c8dd75f9d15c_*.py:26-30
```python
op.execute("""UPDATE document_schemas SET vertical='fraud' WHERE document_type='OBITUARY';""")
```
House style. Use parameter binding for the embedded strings (they contain apostrophes / long text).

### JSONB_FIELD_EDIT
// SOURCE: backend/alembic/versions/c8dd75f9d15c_*.py:48-61
```python
SET schema_fields = (
  SELECT jsonb_agg(CASE WHEN elem->>'name'='owner_occupied'
                        THEN jsonb_set(elem,'{description}', :desc::jsonb) ELSE elem END)
  FROM jsonb_array_elements(schema_fields) AS elem)
```
The downgrade restores descriptions with the SAME jsonb_agg/jsonb_set idiom upgrade used — only the
target string differs (canonical original instead of cleaned).

### MIGRATION_IN_TESTS
// SOURCE: backend/tests/conftest.py:30-31, 60-63
```python
cfg = Config("alembic.ini"); command.downgrade(cfg, "d4e9f2a83b17")
```

---

## Files to Change

| File | Action | Justification |
|---|---|---|
| `backend/alembic/versions/c8dd75f9d15c_schema_cleanup_obituary_and_sr_.py` | UPDATE | Add canonical-original constants; rewrite `downgrade()` to restore them. Leave `upgrade()` unchanged. |
| `backend/tests/test_migration_c8dd75f9d15c.py` | CREATE | Controlled round-trip test over all three changed surfaces. |

## NOT Building
- No change to `upgrade()`.
- No snapshot/backup table.
- No new migration revision.
- No restoration of fields c8dd's upgrade did NOT touch (e.g. `tax_penalty_interest`).
- No attempt to reconstruct arbitrary per-DB manual edits (see Scope Caveat).

---

## Step-by-Step Tasks

### Task 1: Recover canonical originals and embed as constants
- **ACTION**: From git, extract the pre-cleanup strings for exactly the surfaces c8dd changed; embed as module-level constants in the migration.
- **IMPLEMENT**:
  - `_ORIGINAL_DESCRIPTIONS`: dict keyed by `(document_type, field_name)` → original description. The five entries (verbatim from `6f655fa` `-` lines):
    - `("PARCEL-RECORD","owner_occupied")`: `"Whether the property is owner-occupied. N on a nonprofit-owned residential property is a signal."`
    - `("990","gov_related_entity")`: `"IRS990/RelatedEntityInd — does org have related entities? False when known related entities exist = SR-025 signal"`
    - `("SOS-FILING","law_firm_filer")`: `"Name of law firm or attorney that submitted the filing — repeated appearance of same firm across entities is a network signal"`
    - `("BUILDING-PERMIT","contractor_name")`: `"Contractor or builder name — second part of the OWNER OR BUILDER field after the slash. Repeated appearance of the same contractor across an entity's permits is a network signal."`
    - `("BUILDING-PERMIT","estimated_value")`: `"Estimated construction value in dollars. Compare to organization's annual revenue to detect SR-026 CONSTRUCTION_OVERAGE signal."`
  - `_ORIGINAL_PROMPTS`: dict keyed by `document_type` → full original `extraction_prompt`, for `990`, `UCC`, `BUILDING-PERMIT`. Pull the COMPLETE original prompt strings from git (do not reconstruct from hunks).
- **EXACT SOURCE COMMANDS** (run these; copy output verbatim into constants):
  ```bash
  # Full pre-cleanup seed file (the source of truth for both prompts and descriptions):
  git show 6f655fa^:backend/app/seeds/document_schemas.py > /tmp/seed_original.py
  # The exact cleanup diff (originals are the '-' lines), for cross-checking:
  git show 6f655fa -- backend/app/seeds/document_schemas.py
  ```
  Locate each `extraction_prompt=` / `EXTRACTION_PROMPT` block for 990 (≈line 794), UCC (≈1069),
  BUILDING-PERMIT in `/tmp/seed_original.py` and copy the whole prompt string.
- **MANDATORY VERIFICATION (per review — highest-error step)**: after pasting constants, prove
  they match git, do not eyeball:
  ```bash
  # 1. The pre-cleanup seed has exactly 5 SR-0 references (2 desc + 3 prompt). Your constants
  #    module must contain the same 5:
  git show 6f655fa^:backend/app/seeds/document_schemas.py | grep -cE 'SR-0[0-9]+'   # => 5
  grep -cE 'SR-0[0-9]+' <the_migration_file>                                         # => 5
  # 2. Diff each pasted prompt against git output (must be empty):
  #    extract your _ORIGINAL_PROMPTS['990'] to a file and:
  diff <(printf '%s' "$YOUR_990_PROMPT") <(git show 6f655fa^:... | sed -n '<range>p')
  ```
  Do NOT proceed to Task 2 until the SR-0 counts match (5 == 5) and the prompt diffs are empty.
- **MIRROR**: INLINE_SEED_CONSTANTS.
- **IMPORTS**: `import sqlalchemy as sa` (for `sa.text(...).bindparams(...)`).
- **GOTCHA**: Strings contain apostrophes and em-dashes — use bound parameters, never f-string interpolation into SQL. Use a triple-quoted raw string for the multi-line prompts. The prompt restore is a *full-prompt overwrite* (canonical), not a token re-insert; intentional per the Scope Caveat.
- **VALIDATE**: constants import cleanly; `len(_ORIGINAL_DESCRIPTIONS)==5`, `len(_ORIGINAL_PROMPTS)==3`; the two SR-0 count checks above both return 5.

### Task 2: Rewrite `downgrade()` to restore canonical values
- **ACTION**: Replace the partial downgrade (and its "not implemented" comment) with: vertical restore + prompt restore (3 types) + description restore (5 fields), all guarded by `document_type` and `vertical='general'`.
- **IMPLEMENT**:
  ```python
  def downgrade() -> None:
      bind = op.get_bind()
      # 1. OBITUARY back to general
      op.execute("UPDATE document_schemas SET vertical='general' WHERE document_type='OBITUARY';")
      # 2. Restore full original prompts (canonical pre-cleanup)
      for dtype, prompt in _ORIGINAL_PROMPTS.items():
          bind.execute(sa.text("""
              UPDATE document_schemas SET extraction_prompt = :p
              WHERE document_type = :t AND vertical = 'general'
          """).bindparams(p=prompt, t=dtype))
      # 3. Restore field descriptions via jsonb_set, one field at a time
      for (dtype, field), desc in _ORIGINAL_DESCRIPTIONS.items():
          bind.execute(sa.text("""
              UPDATE document_schemas
              SET schema_fields = (
                  SELECT jsonb_agg(CASE WHEN elem->>'name' = :f
                                        THEN jsonb_set(elem, '{description}', to_jsonb(CAST(:d AS text)))
                                        ELSE elem END)
                  FROM jsonb_array_elements(schema_fields) AS elem)
              WHERE document_type = :t AND vertical = 'general'
          """).bindparams(f=field, d=desc, t=dtype))
  ```
- **MIRROR**: RAW_SQL_EXECUTE, JSONB_FIELD_EDIT, INLINE_SEED_CONSTANTS.
- **GOTCHA**: Use `to_jsonb(CAST(:d AS text))` — NOT `to_jsonb(:d::text)`. A `::text` cast adjacent to a SQLAlchemy bind param is parser-ambiguous; the explicit `CAST(... AS text)` form is unambiguous and identical in behavior. It produces a correctly-escaped JSON string (handles the apostrophe in "entity's"); do NOT hand-build `'"..."'::jsonb`. Each description UPDATE is scoped to its `document_type` so the same `field` name in another schema is untouched.
- **VALIDATE**: see Task 3.

### Task 3: Controlled round-trip reversibility test
- **ACTION**: Create `backend/tests/test_migration_c8dd75f9d15c.py`. Because `setup_db` truncates `document_schemas`, the test seeds its own controlled pre-cleanup rows.
- **IMPLEMENT** (flow per review):
  1. `command.downgrade(cfg, "d4e9f2a83b17")`
  2. INSERT controlled rows in **pre-cleanup** state: `OBITUARY` (vertical='general'), `990`/`UCC`/`BUILDING-PERMIT` with prompts containing `SR-0xx`, and `BUILDING-PERMIT` `schema_fields` with `estimated_value` carrying the original SR-026 description.
  3. `command.upgrade(cfg, "c8dd75f9d15c")`
  4. Assert cleaned: OBITUARY vertical=='fraud'; a 990 prompt has no `SR-0` substring; `estimated_value` description == cleaned string.
  5. `command.downgrade(cfg, "d4e9f2a83b17")`
  6. Assert restored: OBITUARY vertical=='general'; the 990 prompt == `_ORIGINAL_PROMPTS['990']`; `estimated_value` description == original SR-026 string.
  7. `finally: command.upgrade(cfg, "head")`
- **GOTCHA — all NOT NULL columns required (verified against `document_schema.py:24-40`)**: at revision `d4e9f2a83b17`, `document_schemas` has these NOT NULL columns whose model `default=` is **Python-side and does NOT apply to raw SQL**, so each controlled INSERT must supply them explicitly: `id`, `document_type`, `vertical`, `display_name`, `schema_fields`, `version`, `is_active`, `parse_strategy`, `default_confidence_threshold`, `created_at`. Only `extraction_prompt` is nullable (but the prompt-bearing rows set it anyway). Insert template:
  ```python
  bind.execute(sa.text("""
      INSERT INTO document_schemas
          (id, document_type, vertical, display_name, schema_fields, extraction_prompt,
           version, is_active, parse_strategy, default_confidence_threshold, created_at)
      VALUES
          (:id, :t, 'general', :dn, CAST(:sf AS jsonb), :ep,
           1, true, 'claude', 0.7, now())
  """).bindparams(id=str(uuid.uuid4()), t=dtype, dn=dtype, sf=json.dumps(fields), ep=prompt))
  ```
  (`import uuid, json`. `parse_strategy` must be one of the enum values `'claude'`/`'xml_direct'`.)
- **MIRROR**: MIGRATION_IN_TESTS; `test_engine` fixture.
- **GOTCHA — unique index (verified)**: `uq_active_schema_type_vertical` (`e1ca59dae292:72-78`) is `UNIQUE (document_type, vertical) WHERE is_active = true`. It rejects only *two active rows sharing the same (document_type, vertical)*. The test inserts ONE active row per distinct `document_type` into a freshly-truncated table → no collision. Each raw-SQL INSERT MUST set `is_active = true` explicitly (the ORM `default=True` does not apply to raw SQL) and a unique `id` (uuid). OBITUARY is inserted `vertical='general'`; `upgrade()` flips it to `'fraud'` — still no collision (different vertical, and no other active OBITUARY row exists).
- **GOTCHA**: The `finally: command.upgrade(cfg,"head")` is mandatory — conftest's session-scoped `migrate_db` and every other test assume head. Keep this test in its own file.
- **VALIDATE**: this test passes AND the full suite stays green (proves the round-trip left head intact).

---

## Testing Strategy

### Assertions (all three changed surfaces — per review Finding 4)
| Surface | After upgrade | After downgrade |
|---|---|---|
| `OBITUARY.vertical` | `fraud` | `general` |
| `990.extraction_prompt` | no `SR-0` substring | `== _ORIGINAL_PROMPTS['990']` |
| `BUILDING-PERMIT` `estimated_value` desc | cleaned string | original SR-026 string |

### Edge Cases Checklist
- [x] downgrade run on a DB lacking the controlled rows → guarded UPDATEs no-op (WHERE matches nothing)
- [x] apostrophe in restored description (`entity's`) → handled by `to_jsonb`/bound params
- [x] same field name in a different `document_type` → unaffected (document_type-scoped WHERE)

---

## Validation Commands

### Static (ruff hook)
```bash
docker-compose run --rm backend ruff check alembic/versions/c8dd75f9d15c_schema_cleanup_obituary_and_sr_.py tests/test_migration_c8dd75f9d15c.py
```
EXPECT: clean

### Targeted test
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_migration_c8dd75f9d15c.py -v
```
EXPECT: pass

### Full suite (no regressions)
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ --ignore=tests/evals -v
```
EXPECT: green

### Manual round-trip
```bash
docker-compose exec backend alembic downgrade d4e9f2a83b17 && docker-compose exec backend alembic upgrade head
```
EXPECT: no errors

---

## Acceptance Criteria
- [ ] `upgrade()` unchanged
- [ ] `downgrade()` restores vertical + 3 prompts + 5 descriptions to canonical pre-c8dd values
- [ ] Round-trip test asserts ALL THREE surfaces (vertical, prompt, schema_fields)
- [ ] Full suite green; test restores DB to head in `finally`
- [ ] ruff clean
- [ ] Scope Caveat stated in the migration docstring (canonical, not per-DB exact)

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Embedded original prompt copied imprecisely from git | Med | High | **Mechanized check** (Task 1): SR-0 count must equal 5 in both git and the migration; per-prompt `diff` against git output must be empty before Task 2 starts. Not "copy carefully." |
| Restoring a surface c8dd never changed | Low | Med | Constants cover ONLY the upgrade()-changed set; NOT-Building lists `tax_penalty_interest` |
| Round-trip test leaves DB downgraded | Med | High | `try/finally: upgrade head` |
| Unique partial index rejects controlled INSERT | Low | Med | **Verified**: index is `(document_type, vertical) WHERE is_active`; one active row per distinct type → no collision. INSERT sets `is_active=true` + uuid `id` explicitly (Task 3). |
| Over-promising reversibility | — | — | Scope Caveat + docstring state canonical-only restoration |

## Notes
- Review-accepted corrections folded in: Finding 1 (no fragile `UPDATE…FROM` — guarded UPDATEs that
  no-op safely), Finding 2 (test seeds its own rows; doesn't assume fixture data), Finding 3 (snapshot
  approach withdrawn; downgrade-only edit on the shipped migration), Finding 4 (all three surfaces
  asserted), Finding 5 (no unmanaged backup table — moot under this design).
- This is a learning artifact; the discovery that `upgrade()`'s regex prompt-scrub diverges from the
  seed cleanup's whole-line removal is why prompts are restored as full canonical overwrites.
