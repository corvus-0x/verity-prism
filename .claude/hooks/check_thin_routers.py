#!/usr/bin/env python3
"""PostToolUse guard: keep routers thin (no direct DB access).

CLAUDE.md: "Routers are thin: validate input -> call service -> return response.
Business logic lives in app/services/." A db.query/add/commit/flush inside a
router is business logic leaking into the HTTP layer.

# WALKTHROUGH: this guard exists because the convention had silently drifted —
# nearly every router was doing its own DB work despite the documented rule.
# After the thin-router refactor, every router delegates to a service, so this
# check is silent on the whole codebase today. It only speaks up when a NEW
# db.* call reappears in a router — catching the drift the moment it starts,
# instead of letting it accumulate again. The match is on `db.`/`session.`
# followed by a data verb, so passing `db` as an argument (e.g. audit.log(db, ...))
# or declaring `Depends(get_db)` does not trip it.

Exit codes: 0 = pass (silent). 2 = fail (message to stderr, surfaced to Claude).
"""

import json
import re
import sys

# db.query( / session.add( / db.commit( ... — data access verbs only.
DB_OP_RE = re.compile(
    r"\b(?:db|session)\.(?:query|add|commit|flush|delete|merge|execute|refresh|"
    r"bulk_save_objects|bulk_insert_mappings)\("
)


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    file_path = data.get("tool_input", data).get("file_path", "")
    norm = file_path.replace("\\", "/")
    if "app/routers/" not in norm or not norm.endswith(".py"):
        return 0

    try:
        content = open(file_path, encoding="utf-8").read()
    except OSError:
        return 0

    hits = sorted({m.group(0) for m in DB_OP_RE.finditer(content)})
    if hits:
        ops = ", ".join(hits)
        sys.stderr.write(
            f"Thin-router guard: this router calls {ops} directly. Routers should "
            f"validate input, call a service in app/services/, and return the result. "
            f"Move the DB logic into a service function (see e.g. note_service, "
            f"document_service) and call it from the endpoint.\n"
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
