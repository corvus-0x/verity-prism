#!/usr/bin/env python3
"""PostToolUse guard: flag service queries that forget the soft-delete filter.

Verity Prism soft-deletes everything (CLAUDE.md: "Soft deletes everywhere").
A query on a soft-deletable model that omits `.filter(Model.is_deleted == False)`
silently returns deleted rows — a bug that PASSES TESTS unless a test happens to
seed a deleted row. This guard catches it at edit time instead.

# WALKTHROUGH: This is the "build the system that verifies" idea made concrete.
# Instead of trusting yourself (or an agent) to remember the filter, a check fires
# on every edit to app/services/. The heuristic is deliberately conservative:
# it only complains when a soft-deletable model is queried AND the word
# `is_deleted` appears NOWHERE in the file. That means every existing service
# (which all already filter) stays silent — the hook only speaks up on a genuinely
# new omission. Low false-positive cost is what makes a hook trustworthy; a noisy
# hook gets ignored, which is worse than no hook.

Exit codes: 0 = pass (silent). 2 = fail (message to stderr, surfaced to Claude).
"""

import json
import re
import sys

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

    hits = {m.group(1) for m in QUERY_RE.finditer(content)}
    if hits and "is_deleted" not in content:
        models = ", ".join(sorted(hits))
        sys.stderr.write(
            f"Soft-delete guard: this service queries {models} but never references "
            f"`is_deleted`. Verity Prism soft-deletes everything - add "
            f".filter(<Model>.is_deleted == False) so deleted rows aren't returned, "
            f"or confirm this query intentionally includes deleted rows.\n"
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
