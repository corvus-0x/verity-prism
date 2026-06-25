#!/usr/bin/env python3
"""PostToolUse guard: migrations that create an enum type must drop it on downgrade.

PostgreSQL enum types are independent objects. `op.create_table(...)` with a
named `sa.Enum(..., name="x")` column auto-creates the type, but `op.drop_table`
NEVER drops it, and `alembic --autogenerate` emits the CREATE without a matching
DROP. The orphaned type then breaks any later re-upgrade with
`type "x" already exists`.

# WALKTHROUGH: this guard exists because the bug shipped three times — the initial
# schema (19 orphaned enums), e1ca59dae292, and the chain that surfaced it while
# testing c8dd. The fix is always the same: add `op.execute("DROP TYPE IF EXISTS
# <name>")` (or sa.Enum(name=...).drop(bind)) to downgrade(). The check is a
# heuristic: if a versions/*.py file creates a named enum (or runs CREATE TYPE)
# but contains no DROP TYPE anywhere, it almost certainly forgot the drop. Files
# that already drop their types — including the three fixed this session — stay
# silent, so this only speaks up on NEW migrations that reintroduce the gap.

Exit codes: 0 = pass (silent). 2 = warn (message to stderr, surfaced to Claude).
"""

import json
import re
import sys

# A named enum creation: sa.Enum(...name="x"), postgresql.ENUM(...name="x"),
# or raw CREATE TYPE. [^)] spans newlines, so multi-line Enum(...) calls match.
CREATES_ENUM_RE = re.compile(r"(?:\bEnum\([^)]*name\s*=)|(?:CREATE\s+TYPE)", re.IGNORECASE)
DROPS_TYPE_RE = re.compile(r"DROP\s+TYPE", re.IGNORECASE)


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    file_path = data.get("tool_input", data).get("file_path", "")
    norm = file_path.replace("\\", "/")
    if "alembic/versions/" not in norm or not norm.endswith(".py"):
        return 0

    try:
        content = open(file_path, encoding="utf-8").read()
    except OSError:
        return 0

    if CREATES_ENUM_RE.search(content) and not DROPS_TYPE_RE.search(content):
        sys.stderr.write(
            "Migration enum guard: this migration creates a named enum type but its "
            "downgrade() never drops it. drop_table does NOT drop the enum, so a later "
            "re-upgrade fails with 'type already exists'. Add "
            'op.execute("DROP TYPE IF EXISTS <name>") for each enum to downgrade() '
            "(see 5a4ff7266708 / e1ca59dae292). If the downgrade intentionally keeps "
            "the type, ignore this.\n"
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
