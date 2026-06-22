---
name: encode-correction
description: Turn a correction of AI output into a durable rule so the same category of mistake can't recur. Use when you've just fixed something Claude got wrong (a convention violation, a hallucinated API, a wrong pattern, a missed invariant) and want it encoded instead of forgotten. Invoke as /encode-correction or say "encode this correction".
---

The user just corrected AI output. Do not move on. Encode the correction so this **category** of mistake can't recur, then log it.

This is the core discipline of the project: every repeated manual correction is a signal that the system — not the output — needs to change. You are building the system that verifies; you are not the system.

## The rule of thumb

Prefer the **strongest enforcement that fits**. The four surfaces, ordered by how little they rely on anyone remembering:

| Surface | Use when | Why this strength |
|---|---|---|
| **Hook** (`.claude/settings.local.json`) | The rule is mechanically checkable — a path, string, or AST pattern — and should fire on *every* edit without anyone remembering | Strongest: removes the human from the loop entirely |
| **Skill** (`.claude/skills/<name>/SKILL.md`) | The correction is a recurring *procedure* — a multi-step how-to that will be repeated | Strong: reusable, invoked on demand |
| **CLAUDE.md rule** | A project-wide convention every session must know, but that can't be mechanically checked | Medium: only works when context is loaded |
| **MEMORY entry** (`memory/*.md` + `MEMORY.md`) | A personal preference, a piece of feedback with a "why", or a project fact | Medium: personal, persists across sessions |

When two fit, pick the stronger one. A convention you *can* mechanize (e.g. "queries must filter `is_deleted`") belongs in a **hook**, not just a CLAUDE.md line — prose you have to remember is the weakest control.

## Steps

### 1. Capture the correction precisely

State, in one line each:
- **What the AI did** (the wrong output)
- **What's correct** (the right behavior)
- **Why** it's wrong (the underlying invariant or preference being violated)

### 2. Generalize — is this a category, or a one-off?

Only encode **categories**. Ask: "Will this class of mistake happen again?"

Do **not** encode (just fix and move on) when:
- It's a typo or a one-time factual slip with no pattern
- It's specific to this one file and won't generalize
- The "correct" behavior is genuinely context-dependent and would cause false positives if made a rule

If it's a one-off, say so and stop — over-encoding creates noise that erodes the system.

### 3. Route to the strongest fitting surface

Walk the tree:

```
Is the correct behavior mechanically checkable?
  (a path pattern, a forbidden/required string, an AST shape)
├─ YES → can a check run on every Edit/Write without false positives?
│        ├─ YES → HOOK
│        └─ NO  → CLAUDE.md rule (state it; mechanize later when checkable)
└─ NO  → Is it a repeatable multi-step procedure?
         ├─ YES → SKILL
         └─ NO  → Is it a project-wide convention (vs. a personal preference)?
                  ├─ convention → CLAUDE.md rule
                  └─ preference/feedback/fact → MEMORY entry
```

State which surface you chose and the one-line reason before encoding.

### 4. Encode it

**Hook** — add to `.claude/settings.local.json` under `hooks.PostToolUse` (or `PreToolUse` to block). Match the existing inline-Python style. Scope tightly with a path/filename check so it only fires where relevant (e.g. `app/services/`). Examples of mechanizable Verity Prism invariants:
- Queries on soft-deleted entities must filter `is_deleted == False`
- Service mutations should call `audit.log(...)`
- Routers in `app/routers/` must not contain business logic (stay thin)
- `workspace_id` must never be a Claude-settable tool parameter

**Skill** — scaffold `.claude/skills/<kebab-name>/SKILL.md` with frontmatter (`name`, `description` ending in the invocation form) matching the other project skills. Keep it concrete and Verity-Prism-flavored.

**CLAUDE.md rule** — add a single line under the most relevant existing section (Key design decisions, Test Conventions, Docstring Conventions, etc.). Match the imperative, one-line style. Do not write an essay.

**MEMORY entry** — write `memory/<slug>.md` with the standard frontmatter (`type: user|feedback|project|reference`), then add a one-line pointer to `memory/MEMORY.md`. For `feedback`/`project`, include **Why:** and **How to apply:** lines. Check for an existing file covering it first — update rather than duplicate.

### 5. Verify it actually works

- **Hook:** confirm valid JSON (`python3 -c "import json; json.load(open('.claude/settings.local.json'))"`), then trigger it against a known-bad and known-good case and confirm it fires/stays silent correctly. A hook that doesn't fire is worse than no hook — it creates false confidence.
- **Skill / CLAUDE.md / MEMORY:** confirm the file is written and (for MEMORY/skills) the index/pointer line exists.

Don't claim it's encoded until you've verified.

### 6. Log it — this is the compound record

Append one row to `docs/correction-log.md` (create it from the header below if missing). This ledger is the *proof the system improves over time* — it's the deliberate-investment trail the whole discipline exists to produce.

```markdown
# Correction Log

Every encoded correction. Newest first. See `/encode-correction`.

| Date | Correction (what was wrong) | Surface | Where it lives |
|------|------------------------------|---------|----------------|
```

Add the new row directly under the header line. Keep "what was wrong" to one plain-English clause.

## Done

Report: the category encoded, the surface chosen, the file touched, and the verification result. One short paragraph — then stop.
