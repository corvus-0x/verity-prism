#!/usr/bin/env python3
"""PostToolUse guard: flag service queries that forget the soft-delete filter.

Verity Prism soft-deletes everything (CLAUDE.md: "Soft deletes everywhere").
A query on a soft-deletable model that omits `.filter(Model.is_deleted == False)`
silently returns deleted rows — a bug that PASSES TESTS unless a test happens to
seed a deleted row. This guard catches it at edit time instead.

# WALKTHROUGH: This is the "build the system that verifies" idea made concrete.
# Instead of trusting yourself (or an agent) to remember the filter, a check fires
# on every edit to app/services/. The check is PER-QUERY, not per-file: for each
# `query(<SoftDeletableModel>)` it inspects only that query's own chain (a window
# up to the next blank line) for an `is_deleted` filter. An earlier version only
# checked whether `is_deleted` appeared ANYWHERE in the file, so one filtered query
# silently excused every unfiltered one in the same module — exactly the kind of
# omission this guard exists to catch. Per-query keeps the low-false-positive
# property (every existing service filters within its own chain) while closing
# that hole.

Exit codes: 0 = pass (silent). 2 = fail (message to stderr, surfaced to Claude).
"""

import json
import re
import sys

# How far past a `query(Model)` to look for the matching is_deleted filter. A
# query chain is a single expression; we scan to the next blank line (end of the
# statement block) or this many characters, whichever comes first.
_WINDOW_CHARS = 600

# Models that carry is_deleted (verified against backend/app/models/).
# NOTE: the lead model class is `InvestigationLead`, not `Lead`.
SOFT_DELETABLE = (
    "Brief",
    "ConnectorRun",
    "Document",
    "Entity",
    "Relationship",
    "Finding",
    "InvestigationLead",
    "Note",
    "Transaction",
)

# Matches db.query(Document), select(Entity), session.query(Note.id), ...
QUERY_RE = re.compile(r"\b(?:query|select)\(\s*(" + "|".join(SOFT_DELETABLE) + r")\b")


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # never block on malformed hook input

    file_path = data.get("tool_input", data).get("file_path", "")
    norm = file_path.replace("\\", "/")
    if "app/services/" not in norm or not norm.endswith(".py"):
        return 0

    try:
        content = open(file_path, encoding="utf-8").read()
    except OSError:
        return 0

    unfiltered = set()
    for m in QUERY_RE.finditer(content):
        model = m.group(1)
        window = content[m.start() : m.start() + _WINDOW_CHARS]
        # Limit the window to this statement block (chain ends at the next blank line).
        block = window.split("\n\n", 1)[0]
        if "is_deleted" in block:
            continue
        # Exempt explicit primary-key lookups: `.id ==` / `.id.in_(` target rows the
        # caller already named, so returning a soft-deleted one is the caller's call.
        # The leak this guard exists to stop is COLLECTION queries that silently
        # include deleted rows, which never pin the primary key.
        if f"{model}.id ==" in block or f"{model}.id.in_(" in block:
            continue
        unfiltered.add(model)

    if unfiltered:
        models = ", ".join(sorted(unfiltered))
        sys.stderr.write(
            f"Soft-delete guard: a query on {models} has no `is_deleted` filter in its "
            f"chain. Verity Prism soft-deletes everything - add "
            f".filter(<Model>.is_deleted == False) so deleted rows aren't returned, "
            f"or confirm this query intentionally includes deleted rows.\n"
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
